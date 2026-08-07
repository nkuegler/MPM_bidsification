###############################################################################
# Unified/autodetecting BIDSme prepare plugin
###############################################################################
# Based on plugin_prepare_nk.py, plugin_prepare_terrax_dcm2niix_nk.py,
# and plugin_prepare_loraks_nk.py.
#
# Purpose:
# - keep the shared subject/session/sessions.tsv logic in one place
# - auto-detect which shim-current metadata field is present
# - auto-detect LORAKS files and only apply LORAKS series_id/series_no logic then
# - optionally handle LORAKS sensitivity maps when include_smaps=True
###############################################################################

from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession
import pandas as pd
import numpy as np
import os
import re
import json
from datetime import datetime
import shutil
from pathlib import Path
import logging

try:
    import plugin_helper_functions as helper
except ImportError:
    helper = None

logger = logging.getLogger(__name__)
plugin_path = os.path.dirname(__file__)

# Global variables set by InitEP / lifecycle hooks
nifti_dir = ""
prep_dir = ""
dry_run = False
id_files_dir_name = "id_info"
id_files_dir = ""
base_dir = ""
sessions_tsv_template = None
subN_sessions_dict = {}
ses_dict_populated_for_this_ses = False
data_avail_in_dir = False
current_subjectID = ""
current_sessionID = ""

# Shim-current QC state
shim_current_relevant_recIDs = [
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "kp_afib1_v1f",
    "kp_afib1_v1g",
    "kp_afib1_v1h1",
]
shim_current_candidate_attrs = [
    "ShimSetting",  # dcm2niix/TerraX-style metadata
    "CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent",  # Siemens CSA-style metadata
]
session_shim_currents = None
session_shim_attr = None
session_shim_current_warning_counter = 0
session_shim_current_relevant_sequences_counter = 0

# LORAKS state
available_contrasts_loraks_base = [
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "ernst_kp_mtflash3d",
]
available_contrasts_loraks = list(available_contrasts_loraks_base)
smap_ident = "smaps_kp_mtflash3d"
include_smaps = False
loraks_seen_this_session = False
files_list = []
file_index = -1


def remove_trailing_slash(path):
    return path[:-1] if path.endswith("/") else path


def argument_to_bool(value):
    """Small local fallback so this plugin can run even if helper is absent."""
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


def has_value(value):
    return value not in (None, "", [], {}, "n/a", "N/A")


def get_recording_filename(recording):
    """Return a filename/path robustly across BIDSme currentFile variants."""
    for arg in (True, False):
        try:
            value = recording.currentFile(arg)
            if value:
                return str(value)
        except Exception:
            pass
    return ""


def detect_reconstruction_state(recording):
    """Return 'loraksRsos', 'loraks', or 'standard' from the filename.

    DICOM metadata usually does not contain the word LORAKS; the reconstructed
    NIfTI filename is authoritative. Therefore any filename/path containing
    'loraks' is treated as LORAKS, not only explicit 'rec-loraks' strings.
    """
    fname = get_recording_filename(recording).casefold()
    if "loraksrsos" in fname or "loraks-rsos" in fname or "loraks_rsos" in fname:
        return "loraksRsos"
    if "loraks" in fname:
        return "loraks"
    return "standard"


def detect_shim_attribute(recording):
    """Pick the first non-empty shim-current attribute available in this recording."""
    for attr in shim_current_candidate_attrs:
        try:
            value = recording.getAttribute(attr)
        except Exception:
            value = None
        if has_value(value):
            return attr, value
    return None, None


def get_series_id(str_to_check, recording):
    """Case-insensitive extraction, preserving original filename casing."""
    filename = recording.currentFile(True)
    lower_filename = filename.casefold()
    lower_str = str_to_check.casefold()
    start_pos = lower_filename.find(lower_str)

    if start_pos == -1:
        recording_id_rest = filename.split(str_to_check)[1].split("_rec")[0]
        return f"{str_to_check}{recording_id_rest}"

    original_cased_str = filename[start_pos:start_pos + len(str_to_check)]
    remaining = filename[start_pos + len(str_to_check):]
    recording_id_rest = remaining.split("_rec")[0]
    return f"{original_cased_str}{recording_id_rest}"


def find_smap_modality_local(files, idx):
    """Fallback for helper.find_smap_modality: look forward for the next known contrast."""
    search_files = files[idx + 1:] + files[:idx]
    for fname in search_files:
        low = fname.casefold()
        for contrast in available_contrasts_loraks_base:
            if contrast.casefold() in low:
                return contrast
    return None


def find_smap_modality(files, idx):
    if helper is not None and hasattr(helper, "find_smap_modality"):
        return helper.find_smap_modality(files, idx)
    return find_smap_modality_local(files, idx)



def _extract_loraks_echo_part(filename):
    """Extract echo and part from a LORAKS/dcm2niix-style filename.

    The prepare step must keep these in the prepared recording identity.
    Otherwise all echoes/parts of one contrast+reconstruction collapse into
    the same prepared recording and files can be skipped/overwritten.
    """
    low = filename.casefold()

    echo_match = re.search(r"(?:^|[_-])echo-?(\d+)(?:[_\.]|$)", low)
    echo_no = int(echo_match.group(1)) if echo_match else 0
    echo_label = f"echo-{echo_no:02d}" if echo_no else "echo-unknown"

    if "part-phase" in low or "_phase" in low or low.endswith("_ph.nii") or "_ph." in low:
        part_label = "part-phase"
        part_offset = 1
    elif "part-mag" in low or "_mag" in low:
        part_label = "part-mag"
        part_offset = 0
    else:
        # Most dcm2niix magnitude files do not carry an explicit _mag suffix.
        part_label = "part-mag"
        part_offset = 0

    return echo_no, echo_label, part_label, part_offset


def _loraks_series_no(contrast_index, recon_method, echo_no, part_offset):
    """Create stable, unique prepare series numbers for LORAKS files.

    Old plugin logic used one series number per contrast/reconstruction.
    That is unsafe for multi-echo magnitude/phase data because different
    echoes and parts can then share one prepared recording identity.
    """
    recon_offset = 0 if recon_method == "loraks" else 100
    echo_component = (echo_no if echo_no else 99) * 2
    return int(1000 + contrast_index * 200 + recon_offset + echo_component + part_offset)


def _default_sessions_template_path():
    """Create/use a minimal sessions JSON template when none is supplied."""
    fallback_dir = Path(prep_dir) / ".prepare_id_map"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    fallback = fallback_dir / "sessions_default.json"
    if not fallback.exists():
        fallback.write_text(json.dumps({
            "session_id": {"Description": "BIDS session label"},
            "original_session_id": {"Description": "Original source session identifier"},
            "acq_time": {"Description": "Acquisition time inferred from filename when available"},
            "scanning_institution": {"Description": "Scanning institution"},
            "manufacturer": {"Description": "Scanner manufacturer"},
            "scanner_model": {"Description": "Scanner model"},
            "field_strength": {"Description": "Magnetic field strength"},
            "shim_curr_cons": {"Description": "Shim-current consistency flag"}
        }, indent=2))
    return str(fallback)


class SubjectMissingError(exceptions.SubjectEPError):
    code = 1


class MappingConsistencyError(exceptions.SubjectEPError):
    code = 2


def _strip_prefix(value, prefix):
    value = str(value).strip()
    return value[len(prefix):] if value.startswith(prefix) else value


def _is_bids_like_subject(value):
    value = _strip_prefix(value, "sub-")
    return value.isdigit()


def _is_bids_like_session(value):
    value = _strip_prefix(value, "ses-")
    return value.isdigit() and len(value) <= 2


def canonical_subject_id(value):
    """Return a zero-padded BIDS subject id without the sub- prefix."""
    value = _strip_prefix(value, "sub-")
    if value.isdigit():
        return f"{int(value):03d}"
    return value


def canonical_session_id(value):
    """Return a zero-padded BIDS session id without the ses- prefix."""
    value = _strip_prefix(value, "ses-")
    if value.isdigit() and len(value) <= 2:
        return f"{int(value):02d}"
    return value


def canonical_session_csv_path(bids_subject_id):
    """Final canonical session-map filename: sub-XXX_sessions.csv."""
    sub = canonical_subject_id(bids_subject_id)
    return Path(id_files_dir) / f"sub-{sub}_sessions.csv"


def legacy_session_csv_path(bids_subject_id):
    """Old legacy session-map filename: XXX_sessions.csv. Read fallback only."""
    sub = canonical_subject_id(bids_subject_id)
    return Path(id_files_dir) / f"{sub}_sessions.csv"


def _empty_subject_map():
    return pd.DataFrame({"subjID": [], "bids_subjID": []}, dtype=str)


def _empty_session_map():
    return pd.DataFrame({"sesID": [], "bids_sesID": []}, dtype=str)


def _normalise_mapping_df(df, required_cols):
    """Keep required columns, coerce to stripped strings, and remove blank rows."""
    if df is None or df.empty:
        return pd.DataFrame({col: [] for col in required_cols}, dtype=str)
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    df = df[required_cols].copy()
    for col in required_cols:
        df[col] = df[col].astype(str).str.strip()
        df.loc[df[col].isin(["nan", "None", "NaN"]), col] = ""
    # Drop rows where the original id is blank. These rows cannot be trusted.
    df = df[df[required_cols[0]] != ""].reset_index(drop=True)
    return df


def _read_subject_map(path):
    path = Path(path)
    if not path.exists():
        return _empty_subject_map()
    return _normalise_mapping_df(pd.read_csv(path, dtype=str), ["subjID", "bids_subjID"])


def _read_session_map(canonical_path, legacy_path=None):
    """Read canonical session map first; use legacy only if canonical is absent."""
    canonical_path = Path(canonical_path)
    if canonical_path.exists():
        return _normalise_mapping_df(pd.read_csv(canonical_path, dtype=str), ["sesID", "bids_sesID"]), canonical_path
    if legacy_path is not None and Path(legacy_path).exists():
        logger.warning(f"Canonical session map missing; reading legacy map as fallback: {legacy_path}")
        return _normalise_mapping_df(pd.read_csv(legacy_path, dtype=str), ["sesID", "bids_sesID"]), Path(legacy_path)
    return _empty_session_map(), canonical_path


def _write_csv_atomic(df, path):
    """Write mappings atomically, reducing the chance of half-written CSVs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _validate_subject_map(df, context="subject_ids.csv"):
    df = _normalise_mapping_df(df, ["subjID", "bids_subjID"])
    df["bids_subjID"] = df["bids_subjID"].map(canonical_subject_id)
    if df["subjID"].duplicated().any():
        dup = df.loc[df["subjID"].duplicated(keep=False), "subjID"].tolist()
        raise RuntimeError(f"Duplicate subjID entries in {context}: {dup}")
    if df["bids_subjID"].duplicated().any():
        dup = df.loc[df["bids_subjID"].duplicated(keep=False), "bids_subjID"].tolist()
        raise RuntimeError(f"Duplicate bids_subjID entries in {context}: {dup}")
    return df


def _validate_session_map(df, context="sessions.csv"):
    df = _normalise_mapping_df(df, ["sesID", "bids_sesID"])
    df["bids_sesID"] = df["bids_sesID"].map(canonical_session_id)
    if df["sesID"].duplicated().any():
        dup = df.loc[df["sesID"].duplicated(keep=False), "sesID"].tolist()
        raise RuntimeError(f"Duplicate sesID entries in {context}: {dup}")
    if df["bids_sesID"].duplicated().any():
        dup = df.loc[df["bids_sesID"].duplicated(keep=False), "bids_sesID"].tolist()
        raise RuntimeError(f"Duplicate bids_sesID entries in {context}: {dup}")
    return df


def _next_unused_numeric_id(existing_values, width):
    used = set()
    for value in existing_values:
        value = str(value).strip()
        if value.isdigit():
            used.add(int(value))
    candidate = 1
    while candidate in used:
        candidate += 1
    return f"{candidate:0{width}d}"


def _ensure_protocol_name_from_rec_id(recording):
    """For standard dcm2niix data, ensure ProtocolName exists for ProtocolName-based bidsmap rules.

    This is intentionally conservative: it only fills ProtocolName when the field is absent/empty.
    Existing metadata is never overwritten.
    """
    if recording.Module() != "MRI":
        return
    rec_id = recording.recId()
    if not rec_id:
        return
    try:
        protocol = recording.getAttribute("ProtocolName")
    except Exception:
        protocol = None
    if not has_value(protocol):
        try:
            recording.setAttribute("ProtocolName", rec_id)
        except Exception as exc:
            logger.warning(f"Could not set ProtocolName from recId for {recording.recIdentity(False)}: {exc}")


def InitEP(source: str, destination: str, dry: bool, **kwargs) -> int:
    global nifti_dir, prep_dir, dry_run, id_files_dir, base_dir
    global sessions_tsv_template, include_smaps, available_contrasts_loraks

    nifti_dir = remove_trailing_slash(source)
    prep_dir = remove_trailing_slash(destination)
    dry_run = dry
    base_dir = os.path.dirname(nifti_dir)
    id_files_dir = f"{base_dir}/{id_files_dir_name}"
    os.makedirs(id_files_dir, exist_ok=True)

    if helper is not None and hasattr(helper, "argument_to_bool"):
        include_smaps = helper.argument_to_bool(kwargs.get("include_smaps", False))
    else:
        include_smaps = argument_to_bool(kwargs.get("include_smaps", False))
    if include_smaps == -1:
        raise exceptions.InitEPError("Invalid value for 'include_smaps' in plugin options")

    available_contrasts_loraks = list(available_contrasts_loraks_base)
    if include_smaps:
        interleaved = []
        for item in available_contrasts_loraks_base:
            interleaved.append(smap_ident)
            interleaved.append(item)
        available_contrasts_loraks = interleaved

    sessions_tsv_template = kwargs.get("sessions_tsv_template", None)
    if sessions_tsv_template is None or str(sessions_tsv_template).strip() == "":
        sessions_tsv_template = _default_sessions_template_path()
        logger.warning(f"No sessions_tsv_template specified; using fallback template: {sessions_tsv_template}")
    else:
        sessions_tsv_template = str(Path(sessions_tsv_template))

    print("options passed to unified prepare plugin:")
    print(f"- include_smaps: {include_smaps}")
    print(f"Loading sessions_nk.json from {sessions_tsv_template}.")
    return 0


def SubjectEP(scan: BidsSession) -> int:
    """Map original source subject IDs to stable BIDS subject IDs.

    Invariant:
        if subjID already exists in subject_ids.csv, its bids_subjID is reused and never changed.
        if a conflict/duplicate exists, fail loudly instead of silently reindexing.
    """
    global current_subjectID, subN_sessions_dict

    csv_sub_file = Path(id_files_dir) / "subject_ids.csv"
    sub_id_df = _read_subject_map(csv_sub_file)
    sub_id_df = _validate_subject_map(sub_id_df, str(csv_sub_file))

    current_subjectID = str(scan.subject).strip()

    # Preferred path: exact original source ID is already known.
    rows = sub_id_df[sub_id_df["subjID"] == current_subjectID]
    if len(rows):
        mapped = canonical_subject_id(rows.iloc[0]["bids_subjID"])
        scan.subject = mapped
        print(f"Subject ID derived from '{csv_sub_file}'.")
    else:
        # Safety path for already BIDS-like input, e.g. re-running on prepared data.
        # Do not create a new mapping if the BIDS ID already exists.
        if _is_bids_like_subject(current_subjectID):
            candidate = canonical_subject_id(current_subjectID)
            rows = sub_id_df[sub_id_df["bids_subjID"].map(canonical_subject_id) == candidate]
            if len(rows):
                scan.subject = candidate
                current_subjectID = str(rows.iloc[0]["subjID"])
                print(f"Subject already BIDS-like and found in '{csv_sub_file}'.")
            else:
                # Rare case: no existing row but folder already looks BIDS-like.
                # Preserve the BIDS label and record it once.
                scan.subject = candidate
                new_row = pd.DataFrame({"subjID": [current_subjectID], "bids_subjID": [candidate]})
                sub_id_df = pd.concat([sub_id_df, new_row], ignore_index=True)
                print(f"BIDS-like subject not present in '{csv_sub_file}'. Adding stable row.")
        else:
            new_id = _next_unused_numeric_id(sub_id_df["bids_subjID"], width=3)
            new_row = pd.DataFrame({"subjID": [current_subjectID], "bids_subjID": [new_id]})
            sub_id_df = pd.concat([sub_id_df, new_row], ignore_index=True)
            scan.subject = new_id
            print(f"Subject ID not present in '{csv_sub_file}'. Adding new stable mapping.")

    sub_id_df = _validate_subject_map(sub_id_df, str(csv_sub_file))
    if not dry_run:
        _write_csv_atomic(sub_id_df, csv_sub_file)

    print(f"Current subject: {current_subjectID} -> {scan.subject}")
    scan.sub_values["original_id"] = current_subjectID

    with open(sessions_tsv_template, 'r') as f:
        sessions_json = json.load(f)

    subN_sessions_dict = {col: [] for col in list(sessions_json.keys())}
    return 0


def SessionEP(scan: BidsSession) -> int:
    """Map original source session IDs to stable BIDS session IDs for this subject.

    Invariant:
        if sesID already exists in sub-XXX_sessions.csv, its bids_sesID is reused and never changed.
        legacy XXX_sessions.csv is read only as fallback when the canonical file is absent.
        all writes go to sub-XXX_sessions.csv.
    """
    global current_sessionID, subN_sessions_dict
    global file_index, files_list, loraks_seen_this_session

    canonical_csv = canonical_session_csv_path(scan.subject)
    legacy_csv = legacy_session_csv_path(scan.subject)
    ses_id_df, source_csv = _read_session_map(canonical_csv, legacy_csv)
    ses_id_df = _validate_session_map(ses_id_df, str(source_csv))

    current_sessionID = str(scan.session).strip()

    # Preferred path: exact original session ID is already known.
    rows = ses_id_df[ses_id_df["sesID"] == current_sessionID]
    if len(rows):
        mapped = canonical_session_id(rows.iloc[0]["bids_sesID"])
        scan.session = mapped
        print(f"Session ID derived from '{source_csv}'.")
    else:
        # Safety path for already BIDS-like session labels.
        if _is_bids_like_session(current_sessionID):
            candidate = canonical_session_id(current_sessionID)
            rows = ses_id_df[ses_id_df["bids_sesID"].map(canonical_session_id) == candidate]
            if len(rows):
                scan.session = candidate
                current_sessionID = str(rows.iloc[0]["sesID"])
                print(f"Session already BIDS-like and found in '{source_csv}'.")
            else:
                scan.session = candidate
                new_row = pd.DataFrame({"sesID": [current_sessionID], "bids_sesID": [candidate]})
                ses_id_df = pd.concat([ses_id_df, new_row], ignore_index=True)
                print(f"BIDS-like session not present in '{source_csv}'. Adding stable row.")
        else:
            new_id = _next_unused_numeric_id(ses_id_df["bids_sesID"], width=2)
            new_row = pd.DataFrame({"sesID": [current_sessionID], "bids_sesID": [new_id]})
            ses_id_df = pd.concat([ses_id_df, new_row], ignore_index=True)
            scan.session = new_id
            print(f"Session ID not present in '{source_csv}'. Adding new stable mapping.")

    ses_id_df = _validate_session_map(ses_id_df, str(canonical_csv))
    if not dry_run:
        _write_csv_atomic(ses_id_df, canonical_csv)

    if source_csv != canonical_csv and Path(source_csv).exists():
        logger.warning(
            f"Read legacy session map {source_csv}; wrote canonical map {canonical_csv}. "
            "Consider archiving the legacy file after verifying the canonical file."
        )

    print(f"Current session: {current_sessionID} -> {scan.session}")

    for col in list(subN_sessions_dict.keys()):
        subN_sessions_dict[col].append('n/a')

    if 'session_id' in subN_sessions_dict:
        subN_sessions_dict['session_id'][-1] = f"ses-{scan.session}"
    if 'original_session_id' in subN_sessions_dict and current_sessionID:
        subN_sessions_dict['original_session_id'][-1] = current_sessionID

    nii_session_dir = f"{scan.in_path}/nii"
    if not Path(nii_session_dir).is_dir():
        logger.warning(f"Directory '{nii_session_dir}' not found. Shim current consistency check may not be reliable.")
    else:
        subdirs = [d.name for d in Path(nii_session_dir).iterdir() if d.is_dir()]
        if not subdirs:
            logger.warning(f"No sub-directories found in session directory '{nii_session_dir}'. Shim current consistency check may not be reliable.")

    file_index = -1
    files_list = []
    loraks_seen_this_session = False
    return 0


def SequenceEP(recording: object) -> int:
    def extract_datetime(string):
        pattern1 = r's(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})'
        match = re.match(pattern1, string)
        if match:
            return match.group(1)
        pattern2 = r's(\d{12})'
        match = re.match(pattern2, string)
        if match:
            dt = datetime.strptime(match.group(1), '%Y%m%d%H%M')
            return dt.strftime('%Y-%m-%d_%H-%M')
        return None

    global data_avail_in_dir, files_list
    data_avail_in_dir = True

    try:
        current_dir = os.path.dirname(recording.currentFile(False))
        files_list = sorted([
            f for f in os.listdir(current_dir)
            if os.path.isfile(os.path.join(current_dir, f))
            and (f.casefold().endswith('.nii') or f.casefold().endswith('.nii.gz'))
        ])
    except Exception:
        files_list = []

    rec_id = recording.recId()
    if recording.Module() == "MRI" and rec_id.startswith(tuple(shim_current_relevant_recIDs)):
        global session_shim_current_relevant_sequences_counter
        session_shim_current_relevant_sequences_counter += 1

    global ses_dict_populated_for_this_ses, subN_sessions_dict
    if not ses_dict_populated_for_this_ses:
        if 'acq_time' in subN_sessions_dict:
            acq_time = extract_datetime(recording.currentFile(True))
            if acq_time:
                subN_sessions_dict['acq_time'][-1] = acq_time

        if 'scanning_institution' in subN_sessions_dict:
            scan_institution = recording.getAttribute("InstitutionName")
            if scan_institution:
                subN_sessions_dict['scanning_institution'][-1] = scan_institution
            else:
                scan_department = recording.getAttribute("InstitutionalDepartmentName")
                if scan_department == "Department":
                    subN_sessions_dict['scanning_institution'][-1] = "(Pecs)"

        if 'manufacturer' in subN_sessions_dict:
            manufacturer = recording.getAttribute("Manufacturer")
            if manufacturer:
                subN_sessions_dict['manufacturer'][-1] = manufacturer

        if 'scanner_model' in subN_sessions_dict:
            model = recording.getAttribute("ManufacturersModelName") or recording.getAttribute("ManufacturerModelName")
            if model:
                subN_sessions_dict['scanner_model'][-1] = model

        if 'field_strength' in subN_sessions_dict:
            field_strength = recording.getAttribute("MagneticFieldStrength")
            if field_strength:
                subN_sessions_dict['field_strength'][-1] = field_strength

        ses_dict_populated_for_this_ses = True
    return 0


def handle_loraks_recording(recording, recon_method):
    global loraks_seen_this_session
    loraks_seen_this_session = True

    fname_original = recording.currentFile(True)
    fname = fname_original.casefold()
    echo_no, echo_label, part_label, part_offset = _extract_loraks_echo_part(fname_original)

    if include_smaps and smap_ident.casefold() in fname:
        smap_modality = find_smap_modality(files_list, file_index)
        if smap_modality:
            smap_modal_idx = next((i for i, elem in enumerate(available_contrasts_loraks_base)
                                   if smap_modality.casefold() in elem.casefold()), None)
            contrast_index = smap_modal_idx if smap_modal_idx is not None else len(available_contrasts_loraks_base)
            recording.series_id = (
                f"{get_series_id(smap_ident, recording)}_"
                f"{smap_modality}_{recon_method}_{echo_label}_{part_label}"
            )
            recording.series_no = _loraks_series_no(contrast_index, recon_method, echo_no, part_offset) + 10000
            logger.info(f"Detected LORAKS smap recording: {recording.series_id}, series_no={recording.series_no}")
        else:
            logger.warning(f"{recording.recIdentity()}: Unable to determine modality of sensitivity map")
        return

    for ind, contrast_fname in enumerate(available_contrasts_loraks_base):
        if contrast_fname.casefold() in fname:
            # CRITICAL: echo and part must be part of the prepared identity.
            # Without this, echo-1..N and mag/phase share the same series_id/series_no.
            recording.series_id = (
                f"{get_series_id(contrast_fname, recording)}_"
                f"{recon_method}_{echo_label}_{part_label}"
            )
            recording.series_no = _loraks_series_no(ind, recon_method, echo_no, part_offset)
            logger.info(f"Detected LORAKS recording: {recording.series_id}, series_no={recording.series_no}")
            return

    logger.warning(f"{recording.recIdentity()}: LORAKS reconstruction detected, but contrast could not be assigned")


def handle_shim_current_recording(recording):
    global session_shim_currents, session_shim_attr, session_shim_current_warning_counter

    attr, shim_currents = detect_shim_attribute(recording)
    if attr is None:
        logger.warning(f"No shim current metadata found in {recording.currentFile(False)}")
        return

    if session_shim_attr is None:
        session_shim_attr = attr
        logger.info(f"Detected shim-current field for this session: {session_shim_attr}")
    elif session_shim_attr != attr:
        logger.warning(
            f"Shim-current metadata field changed within session: {session_shim_attr} -> {attr}. "
            "This may indicate mixed metadata sources."
        )

    if session_shim_currents is None:
        session_shim_currents = shim_currents
    elif session_shim_currents != shim_currents:
        logger.warning(f"""Shim currents vary in
                              {recording.currentFile(False)}
                              from the rest of the session.
                              The data may be unusable.""")
        session_shim_current_warning_counter += 1


def RecordingEP(recording: object) -> int:
    global file_index

    if recording.Module() != "MRI":
        return 0

    file_index += 1
    recon_state = detect_reconstruction_state(recording)

    # Conservative metadata fallback for standard dcm2niix data.
    # Existing ProtocolName values are preserved.
    if recon_state == "standard":
        _ensure_protocol_name_from_rec_id(recording)

    if recon_state in ("loraks", "loraksRsos"):
        handle_loraks_recording(recording, recon_state)
        return 0

    rec_id = recording.recId()
    if rec_id.startswith(tuple(shim_current_relevant_recIDs)):
        handle_shim_current_recording(recording)

    return 0


def FileEP(path: str, recording: object) -> int:
    return 0


def SequenceEndEP(path: str, recording: object) -> int:
    return 0


def SessionEndEP(scan: BidsSession) -> int:
    global data_avail_in_dir, session_shim_current_warning_counter
    global session_shim_current_relevant_sequences_counter, subN_sessions_dict
    global session_shim_currents, session_shim_attr, ses_dict_populated_for_this_ses
    global loraks_seen_this_session

    if dry_run:
        return 0

    if data_avail_in_dir:
        column_ses_dict = list(subN_sessions_dict.keys())
        logger.info(f"Number of sequences relevant for shim current consistency check: {session_shim_current_relevant_sequences_counter}")
        logger.info(f"LORAKS data detected in this session: {loraks_seen_this_session}")

        if session_shim_current_relevant_sequences_counter in (0, 1):
            if 'shim_curr_cons' in column_ses_dict:
                logger.warning(f"No information about shim current consistency available in {scan.session} of {scan.subject}.")
                subN_sessions_dict['shim_curr_cons'][-1] = 'n/a'
        else:
            if session_shim_current_warning_counter == 0 and session_shim_currents is not None:
                logger.info("No shim current inconsistencies present in this session!")
                if 'shim_curr_cons' in column_ses_dict:
                    subN_sessions_dict['shim_curr_cons'][-1] = 'consistent'
            elif session_shim_current_warning_counter == 0 and session_shim_currents is None:
                logger.warning("Relevant sequences were present, but no shim-current field could be read.")
                if 'shim_curr_cons' in column_ses_dict:
                    subN_sessions_dict['shim_curr_cons'][-1] = 'n/a'
            else:
                logger.warning(f"Shim currents are INCONSISTENT in this {scan.session} of {scan.subject}! The data may be unusable.")
                if 'shim_curr_cons' in column_ses_dict:
                    subN_sessions_dict['shim_curr_cons'][-1] = 'inconsistent'
    else:
        logger.warning(f"No NIfTI data found in the directories of subject '{current_subjectID}' session '{current_sessionID}'.")

    logger.info("--------------")

    session_shim_currents = None
    session_shim_attr = None
    session_shim_current_warning_counter = 0
    session_shim_current_relevant_sequences_counter = 0
    ses_dict_populated_for_this_ses = False
    data_avail_in_dir = False
    loraks_seen_this_session = False
    return 0


def SubjectEndEP(scan: BidsSession) -> int:
    global subN_sessions_dict

    print(f"""{scan.subject}_sessions.tsv:
          {subN_sessions_dict}
          ------------------------------------
          """)

    df_sessions = pd.DataFrame(subN_sessions_dict)
    if (Path(prep_dir) / scan.subject).is_dir():
        output_filename_tsv = f"{prep_dir}/{scan.subject}/{scan.subject}_sessions.tsv"
        df_sessions.to_csv(output_filename_tsv, sep='\t', index=False)

        output_filename_json = f"{prep_dir}/{scan.subject}/{scan.subject}_sessions.json"
        if sessions_tsv_template and Path(sessions_tsv_template).exists():
            shutil.copyfile(sessions_tsv_template, output_filename_json)
        else:
            logger.warning(f"No sessions JSON template available; not writing {output_filename_json}")

    subN_sessions_dict = {}
    return 0


def FinaliseEP() -> int:
    return 0