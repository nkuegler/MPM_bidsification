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
    try:
        return recording.currentFile(True)
    except Exception:
        return ""


def detect_reconstruction_state(recording):
    """Return 'loraksRsos', 'loraks', or 'standard' from the filename."""
    fname = get_recording_filename(recording).casefold()
    if "rec-loraksrsos" in fname:
        return "loraksRsos"
    if "rec-loraks" in fname:
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


class SubjectMissingError(exceptions.SubjectEPError):
    code = 1


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
    if sessions_tsv_template is None:
        raise exceptions.InitEPError("No sessions_tsv_template specified in plugin options")
    sessions_tsv_template = str(Path(sessions_tsv_template))

    print("options passed to unified prepare plugin:")
    print(f"- include_smaps: {include_smaps}")
    print(f"Loading sessions_nk.json from {sessions_tsv_template}.")
    return 0


def SubjectEP(scan: BidsSession) -> int:
    csv_sub_file = f"{id_files_dir}/subject_ids.csv"

    if not os.path.isfile(csv_sub_file):
        sub_id_df = pd.DataFrame({'subjID': [], 'bids_subjID': []}, dtype=str)
    else:
        sub_id_df = pd.read_csv(csv_sub_file, dtype={'subjID': str, 'bids_subjID': str})

    global current_subjectID
    current_subjectID = scan.subject

    if scan.subject in sub_id_df['subjID'].values:
        scan.subject = f"{int(sub_id_df.loc[sub_id_df['subjID'] == scan.subject, 'bids_subjID'].iloc[0]):03}"
        print(f"Subject ID derived from '{csv_sub_file}'.")
    else:
        print(f"Subject ID not present in '{csv_sub_file}'. Adding and indexing the subject.")
        current_bids_subjID = '001' if sub_id_df.empty else int(np.max(sub_id_df['bids_subjID'].astype(int))) + 1
        new_row = pd.DataFrame({'subjID': [scan.subject], 'bids_subjID': [f"{int(current_bids_subjID):03}"]})
        sub_id_df = pd.concat([sub_id_df, new_row], ignore_index=True)
        scan.subject = f"{int(new_row['bids_subjID'].iloc[0]):03}"

    print(f"Current subject: {current_subjectID} -> {scan.subject}")
    sub_id_df.to_csv(csv_sub_file, index=False)
    scan.sub_values["original_id"] = current_subjectID

    with open(sessions_tsv_template, 'r') as f:
        sessions_json = json.load(f)

    global subN_sessions_dict
    subN_sessions_dict = {col: [] for col in list(sessions_json.keys())}
    return 0


def SessionEP(scan: BidsSession) -> int:
    csv_ses_file = f"{id_files_dir}/{scan.subject}_sessions.csv"

    if not os.path.isfile(csv_ses_file):
        ses_id_df = pd.DataFrame({'sesID': [], 'bids_sesID': []}, dtype=str)
    else:
        ses_id_df = pd.read_csv(csv_ses_file, dtype={'sesID': str, 'bids_sesID': str})

    global current_sessionID
    current_sessionID = scan.session

    if scan.session in ses_id_df['sesID'].values:
        scan.session = f"{int(ses_id_df.loc[ses_id_df['sesID'] == scan.session, 'bids_sesID'].iloc[0]):02}"
        print(f"Session ID derived from '{csv_ses_file}'.")
    else:
        print(f"Session ID not present in '{csv_ses_file}'. Adding and indexing the subject.")
        current_bids_sesID = '01' if ses_id_df.empty else int(np.max(ses_id_df['bids_sesID'].astype(int))) + 1
        new_row = pd.DataFrame({'sesID': [scan.session], 'bids_sesID': [f"{int(current_bids_sesID):02}"]})
        ses_id_df = pd.concat([ses_id_df, new_row], ignore_index=True)
        scan.session = f"{int(new_row['bids_sesID'].iloc[0]):02}"

    print(f"Current session: {current_sessionID} -> {scan.session}")
    ses_id_df.to_csv(csv_ses_file, index=False)

    global subN_sessions_dict
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

    global file_index, files_list, loraks_seen_this_session
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
            if os.path.isfile(os.path.join(current_dir, f)) and '.nii' in f
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

    rsos_factor = 1 if recon_method == "loraksRsos" else 0
    fname = recording.currentFile(True).casefold()

    if include_smaps and smap_ident.casefold() in fname:
        smap_modality = find_smap_modality(files_list, file_index)
        if smap_modality:
            recording.series_id = f"{get_series_id(smap_ident, recording)}_{smap_modality}_{recon_method}"
            smap_modal_idx = next((i for i, elem in enumerate(available_contrasts_loraks)
                                   if smap_modality.casefold() in elem.casefold()), None)
            if smap_modal_idx is not None:
                recording.series_no = int(np.arange(1, len(available_contrasts_loraks * 2), 2)[smap_modal_idx - 1] + rsos_factor)
        else:
            logger.warning(f"{recording.recIdentity()}: Unable to determine modality of sensitivity map")
        return

    for ind, contrast_fname in enumerate(available_contrasts_loraks):
        if contrast_fname.casefold() in fname and contrast_fname != smap_ident:
            recording.series_id = f"{get_series_id(contrast_fname, recording)}_{recon_method}"
            recording.series_no = int(np.arange(1, len(available_contrasts_loraks * 2), 2)[ind] + rsos_factor)
            logger.info(f"Detected LORAKS recording: {recording.series_id}, series_no={recording.series_no}")
            return


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
        shutil.copyfile(sessions_tsv_template, output_filename_json)

    subN_sessions_dict = {}
    return 0


def FinaliseEP() -> int:
    return 0
