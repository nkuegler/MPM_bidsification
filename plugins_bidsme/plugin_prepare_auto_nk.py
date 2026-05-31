###############################################################################
# Unified BIDSme prepare plugin
#
# Patched version:
# - Fixes session remapping bug where raw date folders like 20260409 were treated
#   as already-BIDS-like sessions.
# - Now only short numeric labels like 01 / 02 / ses-01 / ses-02 are treated as
#   existing BIDS session labels.
# - Date-like raw sessions are mapped through <dataset_root>/id_info/<sub>_sessions.csv
#   or temporary .prepare_id_map mappings.
###############################################################################

from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession

import logging
from pathlib import Path
import pandas as pd

try:
    import plugin_helper_functions as helper
except ImportError:
    helper = None


logger = logging.getLogger(__name__)


SHIM_RELEVANT_REC_IDS = (
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "kp_afib1_v1f",
    "kp_afib1_v1g",
    "kp_afib1_v1h1",
)

SHIM_ATTRS = (
    "ShimSetting",
    "CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent",
)

LORAKS_CONTRASTS = (
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "ernst_kp_mtflash3d",
)

SMAP_IDENT = "smaps_kp_mtflash3d"


source_dir = ""
prep_dir = ""
dry_run = False

existing_bids_dir = ""
existing_id_info_dir = ""
temp_map_dir = ""

include_smaps = False

current_original_subject = ""
current_bids_subject = ""
current_original_session = ""
current_bids_session = ""

session_files = []
recording_index = -1

shim_reference = None
shim_attr_used = None
shim_relevant_count = 0
shim_warning_count = 0
loraks_seen = False


class SubjectMissingError(exceptions.SubjectEPError):
    code = 1


def as_bool(value):
    """Parse BIDSme plugin option booleans."""
    if helper is not None and hasattr(helper, "argument_to_bool"):
        parsed = helper.argument_to_bool(value)
        if parsed != -1:
            return parsed

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


def read_csv_or_empty(path, columns):
    """Read a CSV as strings, or return an empty table with the requested columns."""
    path = Path(path)
    if path.is_file():
        df = pd.read_csv(path, dtype=str).fillna("")
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns]
    return pd.DataFrame({col: [] for col in columns}, dtype=str)


def write_csv(path, df):
    """Write a CSV unless this is a dry run."""
    if dry_run:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def infer_dataset_root_from_prepare_destination(destination):
    """
    Infer dataset root from the prepare destination.

    Expected layout:
        <dataset_root>/
            source/
            temp/
            bids/
            id_info/
    """
    dest = Path(destination).resolve()
    parts = list(dest.parts)

    if "temp" in parts:
        temp_idx = parts.index("temp")
        return str(Path(*parts[:temp_idx]))

    return str(dest.parent)


def infer_existing_id_info_dir(destination):
    return str(Path(infer_dataset_root_from_prepare_destination(destination)) / "id_info")


def infer_existing_bids_dir(destination):
    return str(Path(infer_dataset_root_from_prepare_destination(destination)) / "bids")


def next_number_from_tables(existing_df, temp_df, bids_col, width):
    """Choose the next numeric BIDS ID after both existing and temporary mappings."""
    numbers = []

    for df in (existing_df, temp_df):
        if not df.empty and bids_col in df.columns:
            for value in df[bids_col].dropna().astype(str):
                value = value.replace("sub-", "").replace("ses-", "")
                if value.isdigit():
                    numbers.append(int(value))

    next_number = max(numbers) + 1 if numbers else 1
    return f"{next_number:0{width}d}"


def subject_mapping_from_participants_tsv(bids_dir):
    """
    Build subject mapping from participants.tsv if available.
    Expected columns:
        participant_id
        original_id
    """
    participants_tsv = Path(bids_dir) / "participants.tsv"

    if not participants_tsv.is_file():
        return pd.DataFrame({"subjID": [], "bids_subjID": []}, dtype=str)

    df = pd.read_csv(participants_tsv, sep="\t", dtype=str).fillna("")

    if "participant_id" not in df.columns or "original_id" not in df.columns:
        logger.warning(
            f"Found {participants_tsv}, but it does not contain both "
            "'participant_id' and 'original_id'. Cannot use it for subject mapping."
        )
        return pd.DataFrame({"subjID": [], "bids_subjID": []}, dtype=str)

    out = pd.DataFrame({
        "subjID": df["original_id"].astype(str),
        "bids_subjID": (
            df["participant_id"]
            .astype(str)
            .str.replace("sub-", "", regex=False)
        ),
    })

    out = out[(out["subjID"] != "") & (out["bids_subjID"] != "")]
    return out.reset_index(drop=True)


def read_subject_mapping(existing_csv, temp_csv):
    """
    Read subject mapping with priority:
    1. participants.tsv in existing BIDS root
    2. dataset-root id_info/subject_ids.csv
    3. temporary mapping from this prepare run
    """
    participants_df = subject_mapping_from_participants_tsv(existing_bids_dir)
    idinfo_df = read_csv_or_empty(existing_csv, ["subjID", "bids_subjID"])
    temp_df = read_csv_or_empty(temp_csv, ["subjID", "bids_subjID"])

    combined = pd.DataFrame({"subjID": [], "bids_subjID": []}, dtype=str)
    seen = set()

    for df in (participants_df, idinfo_df):
        for _, row in df.iterrows():
            subj = str(row["subjID"])
            if subj and subj not in seen:
                combined = pd.concat([combined, row.to_frame().T], ignore_index=True)
                seen.add(subj)

    return combined, temp_df


def clean_numeric_id(value, width):
    """Convert values such as '007', 'sub-007', or 'ses-02' to fixed-width numeric strings."""
    value = str(value).replace("sub-", "").replace("ses-", "")
    return f"{int(value):0{width}d}"


def lookup_mapping_value(df, original_id, original_col, bids_col):
    """Return mapped value if original_id is present in df, otherwise None."""
    if df.empty or original_col not in df.columns or bids_col not in df.columns:
        return None

    matches = df[df[original_col].astype(str) == str(original_id)]
    if matches.empty:
        return None

    return matches[bids_col].iloc[0]


def get_or_create_mapping(original_id, existing_csv, temp_csv, original_col, bids_col, width):
    """
    Generic mapping function, used for sessions.

    Existing mappings are preferred. New mappings are written only to temp_csv.
    """
    columns = [original_col, bids_col]

    logger.info(f"Looking up mapping for {original_col}={original_id}")
    logger.info(f"Existing mapping CSV: {existing_csv}")
    logger.info(f"Temporary mapping CSV: {temp_csv}")

    existing_df = read_csv_or_empty(existing_csv, columns)
    temp_df = read_csv_or_empty(temp_csv, columns)

    if not existing_df.empty:
        logger.info(f"Existing mapping rows: {existing_df.to_dict(orient='records')}")
    else:
        logger.info("Existing mapping table is empty or not found.")

    value = lookup_mapping_value(existing_df, original_id, original_col, bids_col)
    if value is not None:
        logger.info(f"Found mapping in existing table: {original_id} -> {value}")
        return clean_numeric_id(value, width)

    value = lookup_mapping_value(temp_df, original_id, original_col, bids_col)
    if value is not None:
        logger.info(f"Found mapping in temporary table: {original_id} -> {value}")
        return clean_numeric_id(value, width)

    new_id = next_number_from_tables(existing_df, temp_df, bids_col, width)
    logger.warning(
        f"No existing mapping found for {original_col}={original_id}. "
        f"Creating temporary mapping -> {new_id}"
    )

    temp_df = pd.concat(
        [
            temp_df,
            pd.DataFrame({original_col: [str(original_id)], bids_col: [new_id]})
        ],
        ignore_index=True,
    )
    write_csv(temp_csv, temp_df)

    return new_id


def get_or_create_subject_mapping(original_id, existing_csv, temp_csv):
    """Subject-specific mapping."""
    existing_df, temp_df = read_subject_mapping(existing_csv, temp_csv)

    if original_id in existing_df["subjID"].astype(str).values:
        value = existing_df.loc[
            existing_df["subjID"].astype(str) == str(original_id),
            "bids_subjID"
        ].iloc[0]
        logger.info(f"Subject mapping found in existing BIDS metadata: {original_id} -> {value}")
        return clean_numeric_id(value, 3)

    if original_id in temp_df["subjID"].astype(str).values:
        value = temp_df.loc[
            temp_df["subjID"].astype(str) == str(original_id),
            "bids_subjID"
        ].iloc[0]
        logger.info(f"Subject mapping found in temporary prepare map: {original_id} -> {value}")
        return clean_numeric_id(value, 3)

    new_id = next_number_from_tables(existing_df, temp_df, "bids_subjID", 3)
    temp_df = pd.concat(
        [
            temp_df,
            pd.DataFrame({"subjID": [str(original_id)], "bids_subjID": [new_id]})
        ],
        ignore_index=True,
    )
    write_csv(temp_csv, temp_df)

    logger.info(f"New subject mapping created temporarily: {original_id} -> {new_id}")
    return new_id


def get_shim_value(recording):
    """Return first available shim-current metadata value."""
    for attr in SHIM_ATTRS:
        value = recording.getAttribute(attr)
        if value not in (None, "", [], {}, "n/a", "N/A"):
            return attr, value
    return None, None


def filename_series_base(filename, prefix):
    """
    Recover the protocol-like part from a LORAKS filename.
    """
    low = filename.casefold()
    prefix_low = prefix.casefold()
    start = low.find(prefix_low)

    if start < 0:
        return prefix

    return filename[start:start + len(prefix)] + filename[start + len(prefix):].split("_rec")[0]


def find_smap_target(files, idx):
    """Find which contrast a sensitivity map belongs to by looking at neighboring files."""
    if helper is not None and hasattr(helper, "find_smap_modality"):
        return helper.find_smap_modality(files, idx)

    for neighbour in files[idx + 1:] + files[:idx]:
        low = neighbour.casefold()
        for contrast in LORAKS_CONTRASTS:
            if contrast.casefold() in low:
                return contrast

    return None


def possible_session_mapping_files(id_info_dir, bids_subject):
    """
    Return possible existing session-mapping filenames.

    Different plugin versions used:
        007_sessions.csv
        sub-007_sessions.csv
    """
    clean = str(bids_subject).replace("sub-", "")
    return [
        Path(id_info_dir) / f"{clean}_sessions.csv",
        Path(id_info_dir) / f"sub-{clean}_sessions.csv",
    ]


def choose_existing_session_csv(id_info_dir, bids_subject):
    """
    Pick the first existing session mapping file for this subject.
    If none exists, return the preferred new-style path.
    """
    candidates = possible_session_mapping_files(id_info_dir, bids_subject)

    for path in candidates:
        if path.is_file():
            logger.info(f"Using existing session mapping file: {path}")
            return path

    logger.info(
        "No existing session mapping file found. Checked: "
        + ", ".join(str(p) for p in candidates)
    )
    return candidates[0]


def is_bids_subject_label(value):
    """
    Return True for already-prepared/BIDS-like subject labels:
        sub-007
        007
    """
    value = str(value)
    if value.startswith("sub-"):
        value = value.replace("sub-", "", 1)

    return value.isdigit() and len(value) <= 3


def normalize_bids_subject_label(value):
    """Convert 'sub-007' or '007' to '007'."""
    value = str(value).replace("sub-", "", 1)

    if not value.isdigit() or len(value) > 3:
        raise ValueError(f"Not a valid BIDS subject label: {value}")

    return f"{int(value):03d}"


def is_bids_session_label(value):
    """
    Return True only for already-prepared/BIDS-like session labels:
        ses-02
        02

    Important:
    Raw date-like session folders such as 20260409 must NOT be treated as
    BIDS session labels. They need to be mapped through *_sessions.csv.
    """
    value = str(value)

    if value.startswith("ses-"):
        value = value.replace("ses-", "", 1)

    return value.isdigit() and len(value) <= 2


def normalize_bids_session_label(value):
    """
    Convert 'ses-02' or '02' to '02'.

    Date-like raw session IDs such as 20260409 are intentionally rejected.
    """
    value = str(value).replace("ses-", "", 1)

    if not value.isdigit() or len(value) > 2:
        raise ValueError(f"Not a valid BIDS session label: {value}")

    return f"{int(value):02d}"


# =============================================================================
# BIDSme lifecycle hooks
# =============================================================================

def InitEP(source: str, destination: str, dry: bool, **kwargs) -> int:
    """
    Called once when the plugin is loaded.
    """
    global source_dir, prep_dir, dry_run
    global existing_bids_dir, existing_id_info_dir, temp_map_dir, include_smaps

    source_dir = source.rstrip("/")
    prep_dir = destination.rstrip("/")
    dry_run = dry

    existing_id_info_dir_opt = kwargs.get("existing_id_info_dir", None)
    if existing_id_info_dir_opt is None:
        existing_id_info_dir = infer_existing_id_info_dir(prep_dir)
    else:
        existing_id_info_dir = str(Path(existing_id_info_dir_opt))

    existing_bids_dir = kwargs.get("existing_bids_dir", None)
    if existing_bids_dir is None:
        existing_bids_dir = infer_existing_bids_dir(prep_dir)
    existing_bids_dir = str(Path(existing_bids_dir))

    temp_map_dir = str(Path(prep_dir) / ".prepare_id_map")
    if not dry_run:
        Path(temp_map_dir).mkdir(parents=True, exist_ok=True)

    include_smaps = as_bool(kwargs.get("include_smaps", False))
    if include_smaps == -1:
        raise exceptions.InitEPError("Invalid value for plugin option 'include_smaps'")

    print("options passed to patched unified prepare plugin:")
    print(f"- include_smaps: {include_smaps}")
    print(f"- existing_bids_dir: {existing_bids_dir}")
    print(f"- existing id_info directory: {existing_id_info_dir}")
    print(f"- existing subject mapping: {Path(existing_id_info_dir) / 'subject_ids.csv'}")
    print(f"- participants.tsv fallback: {Path(existing_bids_dir) / 'participants.tsv'}")
    print(f"- temporary mapping directory: {temp_map_dir}")
    print("- final id_info writing: disabled during prepare")
    print("- final sessions.tsv/json writing: disabled during prepare")
    print("- date-like sessions such as 20260409 will be remapped via *_sessions.csv")

    return 0


def SubjectEP(scan: BidsSession) -> int:
    """
    Called when BIDSme enters a source subject folder.
    """
    global current_original_subject, current_bids_subject

    current_original_subject = scan.subject

    if is_bids_subject_label(current_original_subject):
        current_bids_subject = normalize_bids_subject_label(current_original_subject)
        scan.subject = current_bids_subject
        scan.sub_values["original_id"] = current_original_subject
        logger.info(
            f"Subject already looks BIDS/prepared: {current_original_subject} -> {scan.subject}; "
            "not remapping."
        )
        print(f"Current subject: {current_original_subject} -> {scan.subject}")
        return 0

    existing_csv = Path(existing_id_info_dir) / "subject_ids.csv"
    temp_csv = Path(temp_map_dir) / "subject_ids.csv"
    logger.info(f"Subject mapping CSV: {existing_csv}")
    logger.info(f"Temporary subject mapping CSV: {temp_csv}")

    current_bids_subject = get_or_create_subject_mapping(
        original_id=current_original_subject,
        existing_csv=existing_csv,
        temp_csv=temp_csv,
    )

    scan.subject = current_bids_subject
    scan.sub_values["original_id"] = current_original_subject

    print(f"Current subject: {current_original_subject} -> {scan.subject}")

    return 0


def SessionEP(scan: BidsSession) -> int:
    """
    Called when BIDSme enters a session folder within the current subject.
    """
    global current_original_session, current_bids_session
    global session_files, recording_index
    global shim_reference, shim_attr_used, shim_relevant_count, shim_warning_count, loraks_seen

    current_original_session = scan.session

    if is_bids_session_label(current_original_session):
        current_bids_session = normalize_bids_session_label(current_original_session)
        scan.session = current_bids_session
        logger.info(
            f"Session already looks BIDS/prepared: {current_original_session} -> {scan.session}; "
            "not remapping."
        )
        print(f"Current session: {current_original_session} -> {scan.session}")
    else:
        existing_csv = choose_existing_session_csv(existing_id_info_dir, current_bids_subject)

        temp_csv = Path(temp_map_dir) / f"{current_bids_subject}_sessions.csv"

        current_bids_session = get_or_create_mapping(
            original_id=current_original_session,
            existing_csv=existing_csv,
            temp_csv=temp_csv,
            original_col="sesID",
            bids_col="bids_sesID",
            width=2,
        )

        scan.session = current_bids_session

        print(f"Current session: {current_original_session} -> {scan.session}")

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
    Called once for each sequence/recording.
    """
    global session_files, shim_relevant_count

    try:
        folder = Path(recording.currentFile(False)).parent
        session_files = sorted(
            p.name
            for p in folder.iterdir()
            if p.is_file() and ".nii" in p.name
        )
    except Exception:
        session_files = []

    if recording.Module() == "MRI":
        rec_id = recording.recId()
        if rec_id.startswith(SHIM_RELEVANT_REC_IDS):
            shim_relevant_count += 1

    return 0


def RecordingEP(recording: object) -> int:
    """
    Called for every file/recording.
    """
    global recording_index, loraks_seen
    global shim_reference, shim_attr_used, shim_warning_count

    if recording.Module() != "MRI":
        return 0

    recording_index += 1

    filename = recording.currentFile(True)
    filename_low = filename.casefold()
    rec_id = recording.recId()

    if "rec-loraks" in filename_low:
        loraks_seen = True

        recon = "loraksRsos" if "rec-loraksrsos" in filename_low else "loraks"
        rsos_offset = 1 if recon == "loraksRsos" else 0

        contrasts = list(LORAKS_CONTRASTS)
        if include_smaps:
            contrasts = [item for contrast in LORAKS_CONTRASTS for item in (SMAP_IDENT, contrast)]

        prefix = None
        smap_target = None

        if include_smaps and SMAP_IDENT.casefold() in filename_low:
            prefix = SMAP_IDENT
            smap_target = find_smap_target(session_files, recording_index)
        else:
            prefix = next((c for c in LORAKS_CONTRASTS if c.casefold() in filename_low), None)

        if prefix is None:
            logger.warning(f"Could not identify LORAKS contrast in {filename}")
            return 0

        series_base = filename_series_base(filename, prefix)

        if smap_target:
            recording.series_id = f"{series_base}_{smap_target}_{recon}"
            contrast_index = next(
                (i for i, item in enumerate(contrasts) if smap_target.casefold() in item.casefold()),
                1,
            ) - 1
        else:
            recording.series_id = f"{series_base}_{recon}"
            contrast_index = contrasts.index(prefix)

        recording.series_no = 2 * contrast_index + 1 + rsos_offset

        return 0

    if not rec_id.startswith(SHIM_RELEVANT_REC_IDS):
        return 0

    current_attr, current_shim = get_shim_value(recording)

    if current_attr is None:
        logger.warning(f"No shim-current metadata found in {recording.currentFile(False)}")
        return 0

    if shim_attr_used is None:
        shim_attr_used = current_attr
        logger.info(f"Detected shim-current metadata field: {shim_attr_used}")
    elif shim_attr_used != current_attr:
        logger.warning(f"Shim-current metadata field changed within session: {shim_attr_used} -> {current_attr}")

    if shim_reference is None:
        shim_reference = current_shim
    elif shim_reference != current_shim:
        logger.warning(f"Shim currents vary in {recording.currentFile(False)}")
        shim_warning_count += 1

    return 0


def FileEP(path: str, recording: object) -> int:
    return 0


def SequenceEndEP(path: str, recording: object) -> int:
    return 0


def SessionEndEP(scan: BidsSession) -> int:
    """
    Called after a session is finished.
    """
    if shim_relevant_count == 0:
        logger.info("No shim-current-relevant sequences detected in this session.")
    elif shim_relevant_count == 1:
        logger.info("Only one shim-current-relevant sequence detected; consistency cannot be assessed.")
    elif shim_warning_count == 0 and shim_reference is not None:
        logger.info("No shim-current inconsistencies detected in this session.")
    elif shim_reference is None:
        logger.warning("Shim-current-relevant sequences were present, but no shim metadata could be read.")
    else:
        logger.warning("Shim-current inconsistency detected in this session.")

    logger.info(f"Shim-current relevant sequences: {shim_relevant_count}")
    logger.info(f"LORAKS data detected: {loraks_seen}")

    return 0


def SubjectEndEP(scan: BidsSession) -> int:
    logger.info(f"Finished prepare stage for subject: {current_original_subject}")
    return 0


def FinaliseEP() -> int:
    return 0
