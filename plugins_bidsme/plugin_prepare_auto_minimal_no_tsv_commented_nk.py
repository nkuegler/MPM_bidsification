###############################################################################
# Minimal unified/autodetecting BIDSme PREPARE plugin -- NO BIDS TSV WRITING
###############################################################################
#
# IMPORTANT CONCEPTUAL BOUNDARY
# -----------------------------
# This is a PREPARE plugin. It should only affect the intermediate/prepared data
# representation that BIDSme uses while discovering/organising scans.
#
# It must NOT create or append final BIDS metadata tables such as:
#   sub-XXX_sessions.tsv
#   sub-XXX_sessions.json
#   participants.tsv
#
# Reason:
#   During preparation you may point BIDSme at folders while testing, debugging,
#   or exploring incomplete data. If this plugin already appended sessions.tsv
#   rows, unwanted sessions could accidentally become part of the final dataset.
#
# Therefore:
#   - subject/session ID mapping is allowed here
#   - sequence ordering is allowed here
#   - logging/QC checks are allowed here
#   - final BIDS metadata writing belongs in the BIDSIFY plugin
#
# WHAT THIS PLUGIN DOES
# ---------------------
# 1. Creates/updates small ID lookup CSV files in id_info/:
#       subject_ids.csv
#       <subject>_sessions.csv
#
#    These files only say:
#       original subject/session label -> numeric BIDS-style label
#
# 2. Checks shim-current consistency and logs the result.
#    It supports two possible metadata fields:
#       ShimSetting
#       CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent
#
# 3. Detects LORAKS files by filename, e.g. rec-loraks / rec-loraksRsos,
#    and sets recording.series_id / recording.series_no so BIDSme can map them
#    consistently.
#
# WHAT THIS PLUGIN DOES NOT DO
# ----------------------------
# - no sessions.tsv writing
# - no sessions.json copying
# - no participant table writing
# - no final BIDS metadata mutation
#
###############################################################################

from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession

import logging
import os

import pandas as pd

# Some of your earlier plugins use helper functions from plugin_helper_functions.
# This import is optional: the plugin still works without it.
try:
    import plugin_helper_functions as helper
except ImportError:
    helper = None

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================
# Constants are values that should not change while the plugin runs.
# Keeping them here makes the actual BIDSme hook functions easier to read.

# Folder next to the source NIfTI directory where persistent ID lookup tables live.
# These are NOT BIDS metadata files. They are only internal bookkeeping files.
ID_FILES_DIR_NAME = "id_info"

# Only these sequences are used for shim-current consistency checking.
# The idea is that MPM/AFI sequences within a session should have the same shim.
SHIM_RELEVANT_REC_IDS = (
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "kp_afib1_v1f",
    "kp_afib1_v1g",
    "kp_afib1_v1h1",
)

# Candidate metadata fields for shim-current information.
# The first one is typical for dcm2niix/TerraX-style JSON metadata.
# The second one is the older/deeper Siemens CSA/Phoenix metadata path.
SHIM_ATTRS = (
    "ShimSetting",
    "CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent",
)

# LORAKS files are sorted/order-stabilised only for these contrasts.
# If a rec-loraks file contains one of these strings, the plugin can assign
# a deterministic series_id and series_no.
LORAKS_CONTRASTS = (
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "ernst_kp_mtflash3d",
)

# Filename identifier for LORAKS sensitivity maps.
SMAP_IDENT = "smaps_kp_mtflash3d"


# =============================================================================
# RUNTIME STATE
# =============================================================================
# BIDSme calls the functions below in stages. Some information needs to survive
# from one call to the next within one run/session. These globals store that state.
#
# This is normal for BIDSme plugins, but it is also why resetting state at the
# correct hook matters.

# Paths/options initialised by InitEP().
nifti_dir = ""
prep_dir = ""
dry_run = False
id_files_dir = ""
include_smaps = False

# Human/original IDs currently being processed. These are kept only for logging.
current_subject_id = ""
current_session_id = ""

# Sequence/file state used mainly for LORAKS smap matching.
session_files = []          # file names in the current sequence folder
recording_index = -1        # index of the current recording within session_files

# Shim-current QC state for the current session.
shim_reference = None       # first shim-current value encountered in the session
shim_attr_used = None       # metadata field used for shim-current values
shim_relevant_count = 0     # number of relevant MPM/AFI recordings encountered
shim_warning_count = 0      # number of times shim differs from the first value

# Whether LORAKS data were seen in the current session. This is only logged.
loraks_seen = False


class SubjectMissingError(exceptions.SubjectEPError):
    """Custom BIDSme-style exception placeholder kept from the original plugins."""
    code = 1


# =============================================================================
# SMALL HELPERS
# =============================================================================
# There are only three helper functions now. Each exists because it avoids real
# duplication or makes a repeated concept explicit.


def as_bool(value):
    """
    Convert a BIDSme plugin option into a boolean.

    BIDSme/plugin options may arrive as actual booleans or as strings such as:
        "true", "false", "yes", "no", "1", "0"

    Return values:
        True / False  -> valid boolean interpretation
        -1            -> invalid value, handled as an error by InitEP()
    """
    # Prefer your shared helper implementation if it is available.
    if helper is not None and hasattr(helper, "argument_to_bool"):
        return helper.argument_to_bool(value)

    # Local fallback so this plugin is self-contained.
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    value = str(value).strip().lower()
    if value in ("true", "t", "1", "yes", "y"):
        return True
    if value in ("false", "f", "0", "no", "n"):
        return False
    return -1


def next_bids_id(csv_file, original_id, original_col, bids_col, width):
    """
    Return a stable numeric BIDS-style ID for one subject or session.

    This is used twice:
        SubjectEP(): maps original subject labels to 001, 002, 003, ...
        SessionEP(): maps original session labels to 01, 02, 03, ...

    The mapping is saved to a small CSV file, e.g.:
        id_info/subject_ids.csv
        id_info/001_sessions.csv

    Example subject mapping:
        original_id = "Pilot_A"
        returned ID = "001"

    Example session mapping:
        original_id = "2024-05-10"
        returned ID = "01"

    This function writes only these id_info CSV files.
    It does NOT write any final BIDS .tsv metadata files.
    """
    # Load existing mapping table if it exists. Otherwise start a new empty table.
    if os.path.isfile(csv_file):
        df = pd.read_csv(csv_file, dtype={original_col: str, bids_col: str})
    else:
        df = pd.DataFrame({original_col: [], bids_col: []}, dtype=str)

    # If this subject/session was already seen before, reuse the existing ID.
    # This is what keeps labels stable across repeated runs.
    if original_id in df[original_col].values:
        bids_id = df.loc[df[original_col] == original_id, bids_col].iloc[0]

    # Otherwise assign the next free number and append it to the lookup table.
    else:
        number = 1 if df.empty else int(df[bids_col].astype(int).max()) + 1
        bids_id = f"{number:0{width}d}"
        df = pd.concat(
            [df, pd.DataFrame({original_col: [original_id], bids_col: [bids_id]})],
            ignore_index=True,
        )
        df.to_csv(csv_file, index=False)

    # Ensure correct zero-padding even if pandas read the CSV oddly.
    return f"{int(bids_id):0{width}d}"


def nonempty(value):
    """
    Decide whether a metadata value is informative.

    BIDSme/DICOM/JSON metadata can return empty strings, empty lists, None, or
    literal "n/a" values. For shim-current checking, all of those mean:
        "no usable shim-current value found here".
    """
    return value not in (None, "", [], {}, "n/a", "N/A")


# =============================================================================
# BIDSME LIFECYCLE HOOKS
# =============================================================================
# BIDSme calls these functions in a defined order. The exact order is roughly:
#
#   InitEP()
#     SubjectEP(subject)
#       SessionEP(session)
#         SequenceEP(sequence)
#           RecordingEP(recording)
#           FileEP(file)              [empty here]
#         SequenceEndEP(sequence)     [empty here]
#       SessionEndEP(session)
#     SubjectEndEP(subject)           [empty here]
#   FinaliseEP()
#
# In this plugin, only InitEP, SubjectEP, SessionEP, SequenceEP, RecordingEP,
# and SessionEndEP do meaningful work.


def InitEP(source: str, destination: str, dry: bool, **kwargs) -> int:
    """
    Called once when BIDSme loads the plugin.

    Inputs from BIDSme:
        source      -> input/prepared NIfTI source directory
        destination -> preparation output directory
        dry         -> dry-run flag
        kwargs      -> plugin options from the BIDSme command/config

    What happens here:
        1. Store paths globally so later hooks can access them.
        2. Create id_info/ for subject/session lookup CSV files.
        3. Read include_smaps option.

    What deliberately does NOT happen here:
        - no sessions.tsv creation
        - no sessions.json copying
        - no BIDS metadata writing
    """
    global nifti_dir, prep_dir, dry_run, id_files_dir, include_smaps

    nifti_dir = source.rstrip("/")
    prep_dir = destination.rstrip("/")
    dry_run = dry

    # id_info lives next to the NIfTI source directory.
    # This means repeated prepare/bidsify runs can reuse the same ID mapping.
    id_files_dir = os.path.join(os.path.dirname(nifti_dir), ID_FILES_DIR_NAME)
    os.makedirs(id_files_dir, exist_ok=True)

    # include_smaps controls whether LORAKS sensitivity maps should be included
    # in the LORAKS ordering logic.
    include_smaps = as_bool(kwargs.get("include_smaps", False))
    if include_smaps == -1:
        raise exceptions.InitEPError("Invalid value for plugin option 'include_smaps'")

    print("options passed to minimal unified prepare plugin:")
    print(f"- include_smaps: {include_smaps}")
    print("- metadata TSV/JSON writing: disabled during preparation")

    return 0


def SubjectEP(scan: BidsSession) -> int:
    """
    Called once when BIDSme enters a subject folder.

    BIDSme passes a BidsSession object called scan.
    Despite the name, this object also stores the current subject/session labels.

    What happens here:
        original subject label -> stable numeric subject label

    Example:
        scan.subject = "Pilot_A"
        becomes
        scan.subject = "001"

    This affects how downstream prepared output is named.
    It does NOT write participants.tsv.
    """
    global current_subject_id

    # Keep original label for logging/debugging.
    current_subject_id = scan.subject

    # Replace scan.subject with a stable numeric label.
    scan.subject = next_bids_id(
        os.path.join(id_files_dir, "subject_ids.csv"),
        current_subject_id,
        "subjID",
        "bids_subjID",
        3,
    )

    print(f"Current subject: {current_subject_id} -> {scan.subject}")
    return 0


def SessionEP(scan: BidsSession) -> int:
    """
    Called once when BIDSme enters a session folder.

    What happens here:
        1. original session label -> stable numeric session label
        2. reset all per-session state

    Example:
        scan.session = "2024-05-10"
        becomes
        scan.session = "01"

    The reset is important because shim-current consistency should be evaluated
    within one session only, not across subjects/sessions.
    """
    global current_session_id, session_files, recording_index
    global shim_reference, shim_attr_used, shim_relevant_count, shim_warning_count, loraks_seen

    # Keep original session label for logging/debugging.
    current_session_id = scan.session

    # Replace scan.session with a stable numeric label for this subject.
    scan.session = next_bids_id(
        os.path.join(id_files_dir, f"{scan.subject}_sessions.csv"),
        current_session_id,
        "sesID",
        "bids_sesID",
        2,
    )

    print(f"Current session: {current_session_id} -> {scan.session}")

    # Reset per-session state.
    # Everything below belongs only to the current session.
    session_files = []
    recording_index = -1
    shim_reference = None
    shim_attr_used = None
    shim_relevant_count = 0
    shim_warning_count = 0
    loraks_seen = False

    return 0


def SequenceEP(recording: object) -> int:
    """
    Called once at the start of each sequence.

    In this minimal plugin, SequenceEP does only one thing:
        store the list of NIfTI files in the current folder.

    Why is this needed?
        LORAKS sensitivity maps do not always encode their target contrast in a
        perfectly explicit way. The old plugins inferred the target contrast by
        looking at neighbouring files/sequences. We preserve that behavior here.

    If this fails, session_files becomes an empty list and LORAKS smap inference
    may be less informative, but normal non-smap processing is unaffected.
    """
    global session_files

    try:
        # recording.currentFile(False) should return the current file path.
        # We take its folder and list all NIfTI files inside it.
        folder = os.path.dirname(recording.currentFile(False))
        session_files = sorted(
            name for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name)) and ".nii" in name
        )
    except Exception:
        # Do not crash preparation just because a file listing failed.
        # The only feature affected is LORAKS smap target inference.
        session_files = []

    return 0


def RecordingEP(recording: object) -> int:
    """
    Called once per recording/file.

    This is the main logic hook.

    It handles two separate cases:

    CASE 1: LORAKS files
        If filename contains "rec-loraks", the plugin assigns:
            recording.series_id
            recording.series_no

        This helps BIDSme distinguish/order LORAKS and LORAKS-RSOS variants.

    CASE 2: Non-LORAKS MPM/AFI files
        If rec_id starts with one of SHIM_RELEVANT_REC_IDS, the plugin checks
        whether shim currents are identical across the session.

    These cases are intentionally mutually exclusive:
        LORAKS files -> LORAKS ordering
        non-LORAKS relevant files -> shim-current QC

    No final BIDS metadata tables are written here.
    """
    global recording_index, loraks_seen
    global shim_reference, shim_attr_used, shim_relevant_count, shim_warning_count

    # Ignore non-MRI modules completely.
    if recording.Module() != "MRI":
        return 0

    # Count recordings within the current session/folder. Used for smap inference.
    recording_index += 1

    filename = recording.currentFile(True)
    filename_low = filename.casefold()
    rec_id = recording.recId()

    # -------------------------------------------------------------------------
    # CASE 1: LORAKS handling
    # -------------------------------------------------------------------------
    # rec-loraks and rec-loraksRsos are reconstructed files. They need stable
    # series_id / series_no values so BIDSme can sort/map them reproducibly.
    if "rec-loraks" in filename_low:
        loraks_seen = True

        # Two reconstruction variants are possible:
        #   rec-loraks      -> recon = loraks
        #   rec-loraksRsos  -> recon = loraksRsos
        # The RSOS variant gets +1 in series_no so it comes next to its partner.
        recon = "loraksRsos" if "rec-loraksrsos" in filename_low else "loraks"
        rsos_offset = 1 if recon == "loraksRsos" else 0

        # Build the contrast ordering list.
        # Without smaps:
        #   T1w, PDw, MTw, Ernst
        # With smaps:
        #   smap, T1w, smap, PDw, smap, MTw, smap, Ernst
        contrasts = list(LORAKS_CONTRASTS)
        if include_smaps:
            contrasts = [item for contrast in LORAKS_CONTRASTS for item in (SMAP_IDENT, contrast)]

        prefix = None       # contrast identifier found in filename
        smap_target = None  # target contrast for a sensitivity map, if applicable

        # Sensitivity maps are special: their filename contains SMAP_IDENT, but
        # the target contrast may need to be inferred from neighbouring files.
        if include_smaps and SMAP_IDENT.casefold() in filename_low:
            prefix = SMAP_IDENT

            # Prefer your existing helper if available because it encodes the
            # original intended smap-neighbour logic.
            if helper is not None and hasattr(helper, "find_smap_modality"):
                smap_target = helper.find_smap_modality(session_files, recording_index)

            # Fallback: look through neighbouring files and find the first known
            # LORAKS contrast appearing in a filename.
            else:
                neighbours = session_files[recording_index + 1:] + session_files[:recording_index]
                for neighbour in neighbours:
                    smap_target = next(
                        (c for c in LORAKS_CONTRASTS if c.casefold() in neighbour.casefold()),
                        None,
                    )
                    if smap_target:
                        break

        # Normal LORAKS contrast file: identify whether this is T1w/PDw/MTw/etc.
        else:
            prefix = next((c for c in LORAKS_CONTRASTS if c.casefold() in filename_low), None)

        # If no known contrast was found, do not crash; just warn and leave the
        # recording unchanged.
        if prefix is None:
            logger.warning(f"Could not identify LORAKS contrast in {filename}")
            return 0

        # Create a series_base from the filename while preserving the original
        # capitalization. Everything up to _rec is retained.
        # Example:
        #   t1w_kp_mtflash3d_v1t3_0p6_rec-loraks_echo-01...
        # becomes something like:
        #   t1w_kp_mtflash3d_v1t3_0p6
        start = filename_low.find(prefix.casefold())
        series_base = filename[start:start + len(prefix)] + filename[start + len(prefix):].split("_rec")[0]

        # Sensitivity map series_id includes its inferred target contrast.
        if smap_target:
            recording.series_id = f"{series_base}_{smap_target}_{recon}"
            contrast_index = next(
                (i for i, item in enumerate(contrasts) if smap_target.casefold() in item.casefold()),
                0,
            ) - 1

        # Normal contrast series_id only includes the reconstruction method.
        else:
            recording.series_id = f"{series_base}_{recon}"
            contrast_index = contrasts.index(prefix)

        # Odd/even scheme:
        #   loraks     -> 1, 3, 5, ...
        #   loraksRsos -> 2, 4, 6, ...
        # The contrast_index determines the base position, rsos_offset chooses
        # the reconstruction variant.
        recording.series_no = 2 * contrast_index + 1 + rsos_offset
        return 0

    # -------------------------------------------------------------------------
    # CASE 2: Shim-current consistency check for non-LORAKS data
    # -------------------------------------------------------------------------
    # Ignore sequences that are not part of the MPM/AFI shim-consistency check.
    if not rec_id.startswith(SHIM_RELEVANT_REC_IDS):
        return 0

    shim_relevant_count += 1

    # Try all known shim-current metadata locations and use the first non-empty
    # value found. This is the autodetection part.
    current_attr = None
    current_shim = None
    for attr in SHIM_ATTRS:
        value = recording.getAttribute(attr)
        if nonempty(value):
            current_attr = attr
            current_shim = value
            break

    # Relevant scan, but no usable shim metadata. Log it, but do not crash.
    if current_attr is None:
        logger.warning(f"No shim-current metadata found in {recording.currentFile(False)}")
        return 0

    # Remember which metadata field worked first. If later recordings use a
    # different field, this may indicate mixed metadata sources.
    if shim_attr_used is None:
        shim_attr_used = current_attr
        logger.info(f"Detected shim-current metadata field: {shim_attr_used}")
    elif shim_attr_used != current_attr:
        logger.warning(f"Shim-current metadata field changed within session: {shim_attr_used} -> {current_attr}")

    # The first shim value becomes the reference. All later relevant recordings
    # should match it.
    if shim_reference is None:
        shim_reference = current_shim
    elif shim_reference != current_shim:
        logger.warning(f"Shim currents vary in {recording.currentFile(False)}")
        shim_warning_count += 1

    return 0


def FileEP(path: str, recording: object) -> int:
    """
    Called after an individual file is copied.

    Not needed here.
    Kept because BIDSme expects plugin hook functions to exist.
    """
    return 0


def SequenceEndEP(path: str, recording: object) -> int:
    """
    Called after a sequence has finished.

    Not needed here.
    """
    return 0


def SessionEndEP(scan: BidsSession) -> int:
    """
    Called after all recordings in one session have been processed.

    Here we summarize shim-current QC in the log only.

    Possible statuses:
        n/a          -> too few relevant scans, or no readable shim metadata
        consistent   -> all relevant scans had the same shim value
        inconsistent -> at least one relevant scan differed

    This status is NOT written into sessions.tsv here.
    The bidsify plugin should handle final sessions.tsv updates.
    """
    if shim_relevant_count <= 1 or shim_reference is None:
        shim_status = "n/a"
    elif shim_warning_count == 0:
        shim_status = "consistent"
    else:
        shim_status = "inconsistent"

    logger.info(f"Shim-current relevant sequences: {shim_relevant_count}")
    logger.info(f"Shim-current status for {scan.subject} {scan.session}: {shim_status}")
    logger.info(f"LORAKS data detected: {loraks_seen}")

    return 0


def SubjectEndEP(scan: BidsSession) -> int:
    """
    Called after all sessions for one subject have been processed.

    Intentionally empty.

    In earlier versions, this is where sub-XXX_sessions.tsv was written.
    That is deliberately removed now, because final BIDS metadata updates should
    happen during bidsification only.
    """
    return 0


def FinaliseEP() -> int:
    """
    Called once after the plugin has finished processing everything.

    Nothing to finalise in this minimal prepare plugin.
    """
    return 0
