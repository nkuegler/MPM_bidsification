###############################################################################
# Unified FULL-CUSTOM BIDSme mapper/bidsify plugin for NK/TerraX/dcm2niix/LORAKS data
#
# Merges behavior from:
# - plugin_bidsify_nk.py
# - plugin_bidsify_terrax_dcm2niix_nk.py
# - plugin_bidsify_loraks_nk.py
#
# Design goals:
# - auto-detect available metadata instead of requiring separate plugin files
# - keep normal/TerraX/dcm2niix/LORAKS behavior in one place
# - never blindly overwrite existing .tsv files; merge/update/append instead
###############################################################################

# PATCHED:
# - _is_bids_like_session no longer treats raw date folders like 20260409 as BIDS sessions.
# - _norm_session rejects date-like session values instead of silently formatting them.
#
from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession
import pandas as pd
import numpy as np
import os
import re
import shutil
import sys
import json
from datetime import datetime
from pathlib import Path
import logging

# Try both layouts: helper next to this file, or one directory above.
try:
    import plugin_helper_functions as helper
except ImportError:
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import plugin_helper_functions as helper

logger = logging.getLogger(__name__)

# global variables set by InitEP
prep_dir = ""
bids_dir = ""
dry_run = False
bidsmap_step = False
include_smaps = "auto"
corresponding_bids_data_path = ""

# -----------------------------------------------------------------------------
# ID/session bookkeeping that belongs to the BIDSIFY stage
# -----------------------------------------------------------------------------
# The paired prepare plugin writes temporary mapping CSVs into:
#   <prep_dir>/.prepare_id_map/
# Bidsify reads those temporary mappings and writes/merges durable copies into:
#   <bids_dir>/id_info/
# Bidsify also writes/merges the final BIDS subject sessions TSV:
#   <bids_dir>/sub-XXX/sub-XXX_sessions.tsv
TEMP_ID_MAP_DIRNAME = ".prepare_id_map"
FINAL_ID_MAP_DIRNAME = "id_info"
temp_id_map_dir = ""
final_id_map_dir = ""
sessions_tsv_template = ""
original_subject_id = ""
original_session_id = ""
subject_session_rows = []
current_session_row = None
session_info_done = False

# Known sequence identifiers across the old plugins
shim_current_relevant_recIDs = [
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "kp_afib1_v1f",
    "kp_afib1_v1g",
    "kp_afib1_v1h1",
]

available_contrasts_loraks = [
    "t1w_kp_mtflash3d",
    "pdw_kp_mtflash3d",
    "mtw_kp_mtflash3d",
    "ernst_kp_mtflash3d",
]
smap_ident = "smaps_kp_mtflash3d"
shim_incons_filename = "WARNING_INCONS_SHIMCURR.txt"
shim_noinfo_filename = "WARNING_NOINFO_SHIMCURR.txt"

# session state
session_shim_currents = None
session_shim_current_warning_counter = 0
session_shim_current_relevant_sequences_counter = 0
session_detected_shim_attr = None
session_has_loraks = False

seq_list = []
seq_index = -1

# per-session counters
deprecatedSEMC_run_counter = 0
T1w_mag_run_counter = 0
T1w_ph_run_counter = 0
PDw_mag_run_counter = 0
PDw_ph_run_counter = 0
MTw_mag_run_counter = 0
MTw_ph_run_counter = 0
MP2RAGE_run_counter = 0
AFI_stx_run_counter = 0
AFI_ptx_run_counter = 0
anat_nm_run_counter = 0
tfl_multiMTC_MT_ON_counter = 0
tfl_multiMTC_MT_OFF_counter = 0
smap_T1w_counter = None
smap_PDw_counter = None
smap_MTw_counter = None
fallback_smap_counter = None
head_coil_smap_counter = None
body_coil_smap_counter = None


class SubjectMissingError(exceptions.SubjectEPError):
    code = 1


def _as_bool_or_auto(value, default=False):
    """Parse BIDSme plugin options. Allows true/false-like values and 'auto'."""
    if isinstance(value, str) and value.casefold() == "auto":
        return "auto"
    parsed = helper.argument_to_bool(value)
    if parsed == -1:
        return default
    return parsed


def _is_missing(value):
    if value is None:
        return True
    if value == "":
        return True
    if value == "n/a":
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _get_attr(recording, key):
    try:
        return recording.getAttribute(key)
    except Exception:
        return None


def _detect_shim_attribute(recording):
    """Return the first usable shim-current metadata field present in this recording."""
    candidates = [
        "ShimSetting",  # dcm2niix/TerraX style
        "CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent",  # CSA/SPM style
    ]
    for attr in candidates:
        value = _get_attr(recording, attr)
        if not _is_missing(value):
            return attr, value
    return None, None


def _normalise_image_type(image_type):
    if isinstance(image_type, list):
        return image_type
    if isinstance(image_type, str):
        return [item.strip() for item in image_type.split("\\")]
    if image_type is None:
        return []
    logger.warning(f"Unexpected ImageType format: {image_type}")
    return []


def _set_gradient_correction_fields(recording, image_type):
    """Set acq_suffix/NonlinearGradientCorrection fields for both dcm2niix and CSA-style JSONs."""
    # CSA key is generally absent in dcm2niix JSONs, so absence should not by itself be an error.
    sdc_key = "CSASeriesHeaderInfo/MrPhoenixProtocol/sDistortionCorrFilter/ucMode"
    sDistortionCorrFilter = _get_attr(recording, sdc_key)

    has_dis3d = "DIS3D" in image_type or "3D" in image_type
    has_dis2d = "DIS2D" in image_type or "2D" in image_type

    if "ND" in image_type:
        recording.custom["acq_suffix"] = "-ND"
        if _is_missing(sDistortionCorrFilter) or sDistortionCorrFilter == 1:
            recording.custom["NonlinearGradientCorrection"] = False
            recording.custom["NonlinearGradientCorrectionType"] = "none"
        else:
            logger.warning(
                "{}: ImageType 'ND' and distortion-correction field '{}' do not match".format(
                    recording.recIdentity(), sDistortionCorrFilter
                )
            )
            recording.custom["NonlinearGradientCorrection"] = "n/a"
            recording.custom["NonlinearGradientCorrectionType"] = "n/a"
    else:
        recording.custom["acq_suffix"] = ""
        if (_is_missing(sDistortionCorrFilter) or sDistortionCorrFilter == 4) and has_dis3d:
            recording.custom["NonlinearGradientCorrection"] = True
            recording.custom["NonlinearGradientCorrectionType"] = "3D"
        elif (_is_missing(sDistortionCorrFilter) or sDistortionCorrFilter == 2) and has_dis2d:
            recording.custom["NonlinearGradientCorrection"] = True
            recording.custom["NonlinearGradientCorrectionType"] = "2D"
        elif has_dis3d:
            recording.custom["NonlinearGradientCorrection"] = True
            recording.custom["NonlinearGradientCorrectionType"] = "3D"
        elif has_dis2d:
            recording.custom["NonlinearGradientCorrection"] = True
            recording.custom["NonlinearGradientCorrectionType"] = "2D"
        else:
            recording.custom["NonlinearGradientCorrection"] = "n/a"
            recording.custom["NonlinearGradientCorrectionType"] = "n/a"


def _partial_fourier_fraction(code):
    return {1: 0.5, 2: 0.625, 4: 0.75, 8: 0.875}.get(code, 1)


def _set_partial_fourier_and_parallel(recording):
    """Set PartialFourier, PartialFourierDirection and ParallelAcquisitionTechnique when CSA fields exist."""
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.ERROR)
        phase_code = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/sKSpace/ucPhasePartialFourier")
        slice_code = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/sKSpace/ucSlicePartialFourier")
        phase_pf = _partial_fourier_fraction(phase_code)
        slice_pf = _partial_fourier_fraction(slice_code)

        recording.custom["PartialFourier"] = slice_pf * phase_pf
        if phase_pf < 1 and slice_pf < 1:
            recording.custom["PartialFourierDirection"] = "COMBINATION"
        elif phase_pf < 1:
            recording.custom["PartialFourierDirection"] = "PHASE"
        elif slice_pf < 1:
            recording.custom["PartialFourierDirection"] = "SLICE_SELECT"
        else:
            recording.custom["PartialFourierDirection"] = ""

        pat_mode = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/sPat/ucPATMode")
        if pat_mode == 2:
            recording.custom["ParallelAcquisitionTechnique"] = "GRAPPA"
        elif pat_mode == 16:
            recording.custom["ParallelAcquisitionTechnique"] = "CAIPIRINHA"
        else:
            recording.custom["ParallelAcquisitionTechnique"] = "n/a"
    finally:
        logging.getLogger().setLevel(original_level)


def _set_afi_fields(recording, rec_id):
    if not rec_id.startswith("kp_afib1_v1"):
        return

    # dcm2niix typically stores the two TR images as EchoNumber 1/2; the old TerraX plugin used fixed TRs.
    echo_num = _get_attr(recording, "EchoNumber")
    if echo_num is not None:
        try:
            tr_index = int(echo_num)
            recording.custom["tr_index"] = tr_index
            tr_list = [0.025, 0.125]
            if 1 <= tr_index <= len(tr_list):
                recording.custom["RepetitionTime"] = tr_list[tr_index - 1]
        except Exception:
            recording.custom["tr_index"] = echo_num

    # CSA/SPM fallback: alTR in microseconds or sequence-specific units; preserve original plugin behavior.
    alTR = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/alTR")
    if not _is_missing(alTR):
        if not isinstance(alTR, (list, tuple)):
            alTR = [alTR]
        recording.custom["alTR"] = alTR
        recording.custom["alTR_sorted"] = sorted(alTR)
        if echo_num is not None:
            try:
                idx = int(echo_num) - 1
                if 0 <= idx < len(alTR):
                    # Original plugin sometimes used raw alTR and sometimes seconds. We keep seconds for large us values.
                    val = alTR[idx]
                    recording.custom["RepetitionTime"] = round(val * 1e-6, 10) if isinstance(val, (int, float)) and val > 10 else val
            except Exception:
                pass

    adFree = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/sWipMemBlock/adFree")
    if not isinstance(adFree, list):
        try:
            adFree = list(adFree)
        except Exception:
            adFree = [adFree]
    recording.custom["SpoilingRFPhaseIncrement"] = adFree[6] if len(adFree) > 6 else "n/a"


def _increment_run_counters(recording, rec_id, image_type):
    global T1w_mag_run_counter, T1w_ph_run_counter
    global PDw_mag_run_counter, PDw_ph_run_counter
    global MTw_mag_run_counter, MTw_ph_run_counter
    global MP2RAGE_run_counter, AFI_stx_run_counter, AFI_ptx_run_counter
    global anat_nm_run_counter, deprecatedSEMC_run_counter
    global tfl_multiMTC_MT_ON_counter, tfl_multiMTC_MT_OFF_counter

    if "M" in image_type:
        recording.custom["part"] = "mag"
    if "P" in image_type:
        recording.custom["part"] = "phase"

    if rec_id.startswith("t1w_kp_mtflash3d"):
        if "M" in image_type:
            T1w_mag_run_counter += 1
            recording.custom["T1w_run_counter"] = T1w_mag_run_counter
        if "P" in image_type:
            T1w_ph_run_counter += 1
            recording.custom["T1w_run_counter"] = T1w_ph_run_counter
    elif rec_id.startswith("pdw_kp_mtflash3d"):
        if "M" in image_type:
            PDw_mag_run_counter += 1
            recording.custom["PDw_run_counter"] = PDw_mag_run_counter
        if "P" in image_type:
            PDw_ph_run_counter += 1
            recording.custom["PDw_run_counter"] = PDw_ph_run_counter
    elif rec_id.startswith("mtw_kp_mtflash3d"):
        if "M" in image_type:
            MTw_mag_run_counter += 1
            recording.custom["MTw_run_counter"] = MTw_mag_run_counter
        if "P" in image_type:
            MTw_ph_run_counter += 1
            recording.custom["MTw_run_counter"] = MTw_ph_run_counter
    elif rec_id.startswith("kp_afib1_v1g_4mm_PA") or rec_id.startswith("kp_afib1_v1f_4mm_PA"):
        # Older plugins disagreed whether these are stx or ptx; keep both counters available.
        AFI_stx_run_counter += 1
        AFI_ptx_run_counter += 1
        recording.custom["AFI_stx_run_counter"] = AFI_stx_run_counter
        recording.custom["AFI_ptx_run_counter"] = AFI_ptx_run_counter
    elif rec_id.startswith("kp_afib1_v1h1_4mm_PA"):
        AFI_ptx_run_counter += 1
        recording.custom["AFI_ptx_run_counter"] = AFI_ptx_run_counter
    elif rec_id.startswith("t1_mp2rage_sag"):
        MP2RAGE_run_counter += 1
        recording.custom["MP2RAGE_run_counter"] = MP2RAGE_run_counter
    elif rec_id.casefold().startswith("anat-nm"):
        anat_nm_run_counter += 1
        recording.custom["anat_nm_run_counter"] = anat_nm_run_counter
    elif rec_id.startswith("JS_mod_semc"):
        deprecatedSEMC_run_counter += 1
        recording.custom["deprecatedSEMC_run_counter"] = deprecatedSEMC_run_counter

    if rec_id.startswith("tfl_multiMTC"):
        if "mt_on" in rec_id.casefold() or "mton" in rec_id.casefold():
            tfl_multiMTC_MT_ON_counter += 1
            recording.custom["tfl_multiMTC_MT_ON_counter"] = tfl_multiMTC_MT_ON_counter
            mtc_amplitude = 0
            pulses = _get_attr(recording, "CSASeriesHeaderInfo/MrPhoenixProtocol/sTXSPEC/aRFPULSE") or []
            for pulse in pulses:
                if isinstance(pulse, dict) and pulse.get("tName") in ("sMTC_RF", "SRFExcit"):
                    mtc_amplitude = pulse.get("flAmplitude") or 0
                    break
            recording.custom["mtc_amplitude"] = round(mtc_amplitude, 3)
            recording.custom["mtc_amplitude_int"] = f"{int(mtc_amplitude)}V"
        if "mt_off" in rec_id.casefold() or "mtoff" in rec_id.casefold():
            tfl_multiMTC_MT_OFF_counter += 1
            recording.custom["tfl_multiMTC_MT_OFF_counter"] = tfl_multiMTC_MT_OFF_counter


def _handle_b1_maps(recording, rec_id):
    low = rec_id.casefold()
    if not low.startswith("b1map_"):
        return
    if low.startswith("b1map_3dream"):
        if "refvolt" in low:
            recording.custom["B1acq"] = "3DREAMrefVolt"
        elif "relb1" in low:
            recording.custom["B1acq"] = "3DREAMrelB1"
        else:
            recording.custom["B1acq"] = "3DREAM"
    elif low.startswith("b1map_product"):
        recording.custom["B1acq"] = "product"
    elif low.startswith("b1map_neurospin"):
        if "cp" in low and "mode" in low:
            recording.custom["B1acq"] = "neurospin_CPmode"
        elif "vr" in low:
            recording.custom["B1acq"] = "neurospin_VR"
        else:
            recording.custom["B1acq"] = "neurospin"


def _handle_smap_sequence(recording, rec_id):
    global smap_T1w_counter, smap_PDw_counter, smap_MTw_counter, fallback_smap_counter
    global head_coil_smap_counter, body_coil_smap_counter

    low = rec_id.casefold()
    if not (low.startswith("smap_kp_mtflash3d") or low.startswith("sens_maps_kp_mtflash3d") or low.startswith("smaps_kp_mtflash3d")):
        return

    receive_coil_name = _get_attr(recording, "ReceiveCoilName") or ""
    coil_source = f"{rec_id} {receive_coil_name}".casefold()
    if "head" in coil_source or "32ch" in coil_source or "array" in coil_source:
        current_coil = "head" if "array" not in coil_source else "array"
        head_coil_smap_counter = 1 if not head_coil_smap_counter else head_coil_smap_counter + 1
    elif "body" in coil_source or "_bc" in coil_source or " bc" in coil_source:
        current_coil = "body"
        body_coil_smap_counter = 1 if not body_coil_smap_counter else body_coil_smap_counter + 1
    else:
        current_coil = "unknown"
    recording.custom["ReceiveCoil"] = current_coil

    smap_modality = helper.find_smap_modality(seq_list, seq_index)
    if smap_modality:
        recording.custom["IntendedFor"] = smap_modality
        if isinstance(head_coil_smap_counter, int) and isinstance(body_coil_smap_counter, int):
            increase_value = 1 if head_coil_smap_counter != body_coil_smap_counter else 0
        else:
            increase_value = 1

        if smap_modality == "T1w":
            smap_T1w_counter = 1 if not smap_T1w_counter else smap_T1w_counter + increase_value
            recording.custom["smap_run"] = smap_T1w_counter
        elif smap_modality == "PDw":
            smap_PDw_counter = 1 if not smap_PDw_counter else smap_PDw_counter + increase_value
            recording.custom["smap_run"] = smap_PDw_counter
        elif smap_modality == "MTw":
            smap_MTw_counter = 1 if not smap_MTw_counter else smap_MTw_counter + increase_value
            recording.custom["smap_run"] = smap_MTw_counter
        else:
            raise ValueError(f"Unknown modality returned from helper function: {smap_modality}")
    else:
        msg = f"{recording.recIdentity()}: Unable to determine modality of sensitivity map"
        print(f"WARNING: {msg}") if bidsmap_step else logger.warning(msg)
        recording.custom["IntendedFor"] = "unknown"
        fallback_smap_counter = 1 if not fallback_smap_counter else fallback_smap_counter + 1
        recording.custom["smap_run"] = fallback_smap_counter


def _is_loraks_recording(recording):
    try:
        return "rec-loraks" in recording.currentFile(True).casefold()
    except Exception:
        return False


def _loraks_get_series_id(str_to_check, recording):
    full_string = recording.currentFile(True)
    string_endings = [
        "_0p6", "_0p5_sag", "_0p8", "_caipi", "_4p0",
        "_32Ch", "_array", "_BC", "_body",
    ]
    string_end = next((ending for ending in string_endings if ending in full_string), None)
    if not string_end:
        logger.warning(f"ProtocolName couldn't be derived properly from {full_string}")
        return str_to_check
    pattern = f"({re.escape(str_to_check)}.*?{re.escape(string_end)})"
    match = re.search(pattern, full_string)
    if match:
        return match.group(1)
    logger.warning(f"ProtocolName couldn't be derived properly from {full_string}")
    return str_to_check


def _handle_loraks_recording(recording):
    global session_has_loraks
    session_has_loraks = True

    fname = recording.currentFile(True)
    low = fname.casefold()
    if "rec-loraksrsos" in low:
        recon_method = "loraksRsos"
    else:
        recon_method = "loraks"
    recording.custom["ReconMethod"] = recon_method

    units = _get_attr(recording, "Units")
    if units == "rad" and ("phase" in low or "ph" in low):
        recording.custom["part"] = "phase"
    else:
        recording.custom["part"] = "mag"

    echo_number = re.findall(r"echo-\d+", low)
    if echo_number:
        recording.custom["EchoNumbers"] = f"{int(echo_number[0].split('-')[1]):02d}"
    else:
        logger.error(f"No echo number found in filename: {fname}")

    should_include_smaps = include_smaps is True or (include_smaps == "auto" and smap_ident.casefold() in low)
    if should_include_smaps and smap_ident.casefold() in low:
        smap_modality = helper.find_smap_modality(seq_list, seq_index)
        if smap_modality:
            recording.custom["IntendedFor"] = smap_modality
            recording.setAttribute("ProtocolName", _loraks_get_series_id(smap_ident, recording))
        else:
            logger.warning("{}: Unable to determine modality of sensitivity map".format(recording.recIdentity()))
    else:
        for contrast_fname in available_contrasts_loraks:
            if contrast_fname.casefold() in low:
                recording.setAttribute("ProtocolName", _loraks_get_series_id(contrast_fname, recording))
                break




def _bids_label(prefix, value):
    """Return a BIDS-style label while tolerating values with or without prefix."""
    value = str(value)
    return value if value.startswith(prefix + "-") else f"{prefix}-{value}"



def _dataset_root_from_bids_dir(path):
    """
    Infer dataset root from the BIDS output path.

    Your layout:
        /data/pt_03187/data/in_vivo/
            id_info/
            source/
            temp/
            bids/

    Standard output:
        bids_dir = /data/pt_03187/data/in_vivo/bids
        dataset_root = /data/pt_03187/data/in_vivo

    LORAKS derivative output:
        bids_dir = /data/pt_03187/data/in_vivo/bids/derivatives/LORAKS
        dataset_root = /data/pt_03187/data/in_vivo
    """
    p = Path(path).resolve()
    parts = list(p.parts)

    if "bids" in parts:
        bids_idx = parts.index("bids")
        return Path(*parts[:bids_idx])

    return p.parent


def _dataset_root_id_info_dir():
    """Canonical id_info directory for this dataset layout."""
    return _dataset_root_from_bids_dir(bids_dir) / "id_info"



def _read_temp_mapping(csv_name):
    """
    Read a mapping CSV.

    Priority:
    1. prepare-stage temporary map:
           <prep_dir>/.prepare_id_map/<csv_name>
    2. canonical dataset map:
           <dataset_root>/id_info/<csv_name>

    The fallback is important for reruns or mapper/bidsify calls where the
    temporary map is missing but the canonical id_info table already exists.
    """
    candidates = [
        Path(temp_id_map_dir) / csv_name,
        _dataset_root_id_info_dir() / csv_name,
    ]

    for path in candidates:
        if path.exists():
            logger.info(f"Reading ID mapping from: {path}")
            return pd.read_csv(path, dtype=str).fillna("n/a")

    logger.warning("Could not find ID mapping file. Checked: " + ", ".join(str(p) for p in candidates))
    return None


def _lookup_original_id(csv_name, original_col, bids_col, bids_id):
    """Find original source ID for a numeric BIDS ID using the prepare-stage map."""
    df = _read_temp_mapping(csv_name)
    if df is None or original_col not in df.columns or bids_col not in df.columns:
        return "n/a"
    bids_id = str(bids_id).replace("sub-", "").replace("ses-", "")
    rows = df[df[bids_col].astype(str).str.zfill(len(bids_id)) == bids_id.zfill(len(bids_id))]
    if len(rows):
        return str(rows.iloc[0][original_col])
    return "n/a"


def _merge_csv_files(source_csv, dest_csv):
    """Merge a mapping CSV without blindly overwriting existing rows."""
    source_csv = Path(source_csv)
    dest_csv = Path(dest_csv)
    if not source_csv.exists():
        return

    dest_csv.parent.mkdir(parents=True, exist_ok=True)
    src = pd.read_csv(source_csv, dtype=str).fillna("n/a")

    if not dest_csv.exists():
        src.to_csv(dest_csv, index=False)
        logger.info(f"Created CSV: {dest_csv}")
        return

    dst = pd.read_csv(dest_csv, dtype=str).fillna("n/a")
    all_cols = list(dict.fromkeys(list(dst.columns) + list(src.columns)))
    dst = dst.reindex(columns=all_cols, fill_value="n/a")
    src = src.reindex(columns=all_cols, fill_value="n/a")

    # Prefer the original-id column as the stable key.
    key_col = None
    for candidate in ("subjID", "sesID"):
        if candidate in all_cols:
            key_col = candidate
            break

    if key_col is None:
        merged = pd.concat([dst, src], ignore_index=True).drop_duplicates(ignore_index=True)
        merged.to_csv(dest_csv, index=False)
        logger.info(f"Merged CSV without key: {dest_csv}")
        return

    existing = {str(row[key_col]): idx for idx, row in dst.iterrows()}
    rows_to_append = []
    for _, row in src.iterrows():
        key = str(row[key_col])
        if key in existing:
            idx = existing[key]
            for col, value in row.items():
                if not _is_missing(value):
                    dst.at[idx, col] = value
        else:
            rows_to_append.append(row)

    if rows_to_append:
        dst = pd.concat([dst, pd.DataFrame(rows_to_append, columns=all_cols)], ignore_index=True)

    dst.to_csv(dest_csv, index=False)
    logger.info(f"Updated/appended CSV: {dest_csv}")


def _copy_temp_id_maps_to_final():
    """Copy/merge prepare-stage temporary ID maps into durable final CSVs."""
    if bidsmap_step:
        logger.info("bidsmap_step=True: not writing final ID mapping CSVs during mapper.")
        return

    src_dir = Path(temp_id_map_dir)
    if not src_dir.is_dir():
        logger.warning(f"Temporary prepare mapping directory not found: {src_dir}")
        return
    for src_csv in sorted(src_dir.glob("*.csv")):
        _merge_csv_files(src_csv, Path(final_id_map_dir) / src_csv.name)


def _default_session_columns():
    return [
        "session_id",
        "original_session_id",
        "acq_time",
        "scanning_institution",
        "manufacturer",
        "scanner_model",
        "field_strength",
        "shim_curr_cons",
    ]


def _session_columns_from_template():
    """Use sessions_tsv_template columns when available; otherwise use defaults."""
    if sessions_tsv_template and Path(sessions_tsv_template).exists():
        try:
            with open(sessions_tsv_template, "r") as f:
                template = json.load(f)
            if isinstance(template, dict) and template:
                return list(template.keys())
        except Exception as exc:
            logger.warning(f"Could not read sessions_tsv_template {sessions_tsv_template}: {exc}")
    return _default_session_columns()


def _new_session_row(scan):
    """Create an empty row for sub-XXX_sessions.tsv for the current session."""
    row = {col: "n/a" for col in _session_columns_from_template()}
    if "session_id" in row:
        row["session_id"] = _bids_label("ses", scan.session)
    if "original_session_id" in row:
        row["original_session_id"] = original_session_id
    return row


def _datetime_from_filename(filename):
    """Extract acquisition time from dcm2niix-style filename prefixes when present."""
    match = re.search(r"s(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    match = re.search(r"s(\d{12})", filename)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M").strftime("%Y-%m-%d_%H-%M")
    return None


def _fill_session_row_once(recording):
    """Fill scanner/session metadata once, using the first recording with readable fields."""
    global session_info_done, current_session_row
    if session_info_done or current_session_row is None:
        return

    filename = recording.currentFile(True)

    if "acq_time" in current_session_row:
        value = _datetime_from_filename(filename)
        if value:
            current_session_row["acq_time"] = value

    if "scanning_institution" in current_session_row:
        institution = _get_attr(recording, "InstitutionName")
        department = _get_attr(recording, "InstitutionalDepartmentName")
        if not _is_missing(institution):
            current_session_row["scanning_institution"] = institution
        elif department == "Department":
            current_session_row["scanning_institution"] = "(Pecs)"

    if "manufacturer" in current_session_row:
        value = _get_attr(recording, "Manufacturer")
        if not _is_missing(value):
            current_session_row["manufacturer"] = value

    if "scanner_model" in current_session_row:
        value = _get_attr(recording, "ManufacturersModelName") or _get_attr(recording, "ManufacturerModelName")
        if not _is_missing(value):
            current_session_row["scanner_model"] = value

    if "field_strength" in current_session_row:
        value = _get_attr(recording, "MagneticFieldStrength")
        if not _is_missing(value):
            current_session_row["field_strength"] = value

    session_info_done = True


def _write_subject_sessions_tsv(scan):
    """Merge collected session rows into the final sub-XXX_sessions.tsv."""
    if not subject_session_rows:
        return

    subject_label = _bids_label("sub", scan.subject)
    subject_dir = Path(bids_dir) / subject_label
    subject_dir.mkdir(parents=True, exist_ok=True)

    temp_tsv = subject_dir / f".{subject_label}_sessions.new.tsv"
    final_tsv = subject_dir / f"{subject_label}_sessions.tsv"

    pd.DataFrame(subject_session_rows).fillna("n/a").replace("", "n/a").to_csv(
        temp_tsv, sep="\t", index=False
    )
    _merge_tsv_files(temp_tsv, final_tsv)
    try:
        temp_tsv.unlink()
    except OSError:
        pass

    if sessions_tsv_template:
        final_json = subject_dir / f"{subject_label}_sessions.json"
        if not final_json.exists() and Path(sessions_tsv_template).exists():
            shutil.copyfile(sessions_tsv_template, final_json)
            logger.info(f"Created sessions JSON sidecar: {final_json}")
        elif final_json.exists():
            logger.info(f"Keeping existing sessions JSON sidecar: {final_json}")

def _merge_tsv_files(source_tsv, dest_tsv):
    """Merge source_tsv into dest_tsv without blindly overwriting existing rows.

    If a stable key exists, rows in source update matching rows in destination only where
    source values are informative. New rows are appended below existing rows.
    """
    source_tsv = Path(source_tsv)
    dest_tsv = Path(dest_tsv)
    dest_tsv.parent.mkdir(parents=True, exist_ok=True)

    if not source_tsv.exists():
        return

    src = pd.read_csv(source_tsv, sep="\t", dtype=str).fillna("n/a")
    if not dest_tsv.exists():
        src.to_csv(dest_tsv, sep="\t", index=False, na_rep="n/a")
        logger.info(f"Created TSV: {dest_tsv}")
        return

    dst = pd.read_csv(dest_tsv, sep="\t", dtype=str).fillna("n/a")

    # Preserve all columns from destination first, then add new columns from source.
    all_cols = list(dst.columns)
    for col in src.columns:
        if col not in all_cols:
            all_cols.append(col)
    for col in all_cols:
        if col not in dst.columns:
            dst[col] = "n/a"
        if col not in src.columns:
            src[col] = "n/a"
    dst = dst[all_cols]
    src = src[all_cols]

    key_candidates = [
        ["session_id"],
        ["participant_id"],
        ["subject_id"],
        ["original_session_id"],
    ]
    key_cols = None
    for cand in key_candidates:
        if all(c in all_cols for c in cand):
            key_cols = cand
            break

    if key_cols is None:
        # Generic fallback: append and drop exact duplicates only.
        merged = pd.concat([dst, src], ignore_index=True).drop_duplicates(ignore_index=True)
        merged.to_csv(dest_tsv, sep="\t", index=False, na_rep="n/a")
        logger.info(f"Merged TSV without key columns: {dest_tsv}")
        return

    # Build lookup from key to row index for existing destination rows.
    def key_of(row):
        return tuple(str(row[c]) for c in key_cols)

    key_to_idx = {key_of(row): idx for idx, row in dst.iterrows()}
    rows_to_append = []

    for _, src_row in src.iterrows():
        key = key_of(src_row)
        if key in key_to_idx:
            idx = key_to_idx[key]
            for col in all_cols:
                val = src_row[col]
                # update only with informative values; never erase existing data with n/a/blank
                if not _is_missing(val):
                    dst.at[idx, col] = val
        else:
            rows_to_append.append(src_row)

    if rows_to_append:
        dst = pd.concat([dst, pd.DataFrame(rows_to_append, columns=all_cols)], ignore_index=True)

    dst.to_csv(dest_tsv, sep="\t", index=False, na_rep="n/a")
    logger.info(f"Updated/appended TSV: {dest_tsv}")


def _copy_non_tsv_safely(source_file, dest_file):
    dest_file = Path(dest_file)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    if dest_file.exists():
        logger.info(f"Keeping existing file, not overwriting: {dest_file}")
        return
    shutil.copyfile(source_file, dest_file)
    logger.info(f"Copied file: {source_file} -> {dest_file}")


def _copy_or_merge_subject_metadata(scan):
    """Copy subject-level sidecar metadata; merge TSVs instead of overwriting."""
    subject_sessions_pattern = f"{scan.subject}_sessions"
    subject_dir = Path(bids_dir) / scan.subject
    subject_dir.mkdir(parents=True, exist_ok=True)

    for file_name in os.listdir(scan.in_path):
        if not re.match(subject_sessions_pattern, file_name):
            continue
        prep_file = Path(scan.in_path) / file_name
        bids_file = subject_dir / file_name
        if prep_file.suffix == ".tsv":
            _merge_tsv_files(prep_file, bids_file)
        else:
            _copy_non_tsv_safely(prep_file, bids_file)


def InitEP(source: str, destination: str, dry: bool, **kwargs) -> int:
    global prep_dir, bids_dir, dry_run, bidsmap_step, include_smaps, corresponding_bids_data_path
    global temp_id_map_dir, final_id_map_dir, sessions_tsv_template
    prep_dir = source.rstrip("/")
    bids_dir = destination.rstrip("/")
    dry_run = dry

    temp_id_map_dir = str(Path(prep_dir) / TEMP_ID_MAP_DIRNAME)

    # In this dataset, id_info is canonical at the dataset root, not inside bids/.
    # Example:
    #   /data/pt_03187/data/in_vivo/id_info
    #
    # This replaces the earlier assumption:
    #   /data/pt_03187/data/in_vivo/bids/id_info
    final_id_map_dir = str(_dataset_root_id_info_dir())

    bidsmap_step = kwargs.get("bidsmap_step", False)
    bidsmap_step = helper.argument_to_bool(bidsmap_step)
    if bidsmap_step == -1:
        raise exceptions.InitEPError("Invalid value for 'bidsmap_step' in plugin options")

    include_smaps = kwargs.get("include_smaps", "auto")
    include_smaps = _as_bool_or_auto(include_smaps, default="auto")

    sessions_tsv_template = kwargs.get("sessions_tsv_template", "")
    if sessions_tsv_template:
        sessions_tsv_template = str(Path(sessions_tsv_template))

    # For LORAKS derivatives, original BIDS dataset is normally two levels above: bids/derivatives/LORAKS.
    corresponding_bids_data_path = os.path.abspath(os.path.join(bids_dir, '..', '..'))

    if not dry_run:
        Path(final_id_map_dir).mkdir(parents=True, exist_ok=True)

    print("options passed to plugin:")
    print(f"- bidsmap_step: {bidsmap_step}, {type(bidsmap_step)}")
    print(f"- include_smaps: {include_smaps}, {type(include_smaps)}")
    print(f"- temporary prepare ID maps: {temp_id_map_dir}")
    print(f"- canonical/final CSV ID map output: {final_id_map_dir}")
    print(f"- sessions_tsv_template: {sessions_tsv_template or 'default columns'}")
    print("- mode: auto-detect normal/TerraX/dcm2niix/LORAKS")
    print("- CSV/TSV handling: merge/update/append; no blind overwrite")
    return 0



def _lookup_bids_id(csv_name, original_col, bids_col, original_id):
    """
    Forward lookup from original source ID to canonical BIDS ID.

    Example:
        original 20260417 -> bids 02

    This is needed because during final bidsify BIDSme may enter either:
        ses-02
    or accidentally:
        20260417 / ses-20260417

    The plugin should force the canonical BIDS session label before files are
    written.
    """
    df = _read_temp_mapping(csv_name)
    if df is None:
        return "n/a"

    if original_col not in df.columns or bids_col not in df.columns:
        return "n/a"

    original_id = str(original_id).replace("sub-", "").replace("ses-", "")
    series = df[original_col].astype(str).str.replace("sub-", "", regex=False).str.replace("ses-", "", regex=False)
    matches = df[series == original_id]

    if matches.empty:
        return "n/a"

    return str(matches[bids_col].iloc[0]).replace("sub-", "").replace("ses-", "")


def _is_bids_like_subject(value):
    value = str(value)
    if value.startswith("sub-"):
        value = value.replace("sub-", "", 1)
    return value.isdigit()


def _is_bids_like_session(value):
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


def _norm_subject(value):
    return f"{int(str(value).replace('sub-', '', 1)):03d}"


def _norm_session(value):
    """
    Convert 'ses-02' or '02' to '02'.

    Date-like raw session IDs such as 20260409 are intentionally rejected.
    """
    value = str(value).replace("ses-", "", 1)
    if not value.isdigit() or len(value) > 2:
        raise ValueError(f"Not a valid BIDS session label: {value}")
    return f"{int(value):02d}"


def SubjectEP(scan: BidsSession) -> int:
    global original_subject_id, subject_session_rows

    current = str(scan.subject)

    if _is_bids_like_subject(current):
        # Already prepared/BIDS-like, e.g. sub-007 or 007.
        scan.subject = _norm_subject(current)
        original_subject_id = _lookup_original_id(
            "subject_ids.csv",
            original_col="subjID",
            bids_col="bids_subjID",
            bids_id=scan.subject,
        )
        logger.info(f"Subject already BIDS-like: {current} -> {scan.subject}; original={original_subject_id}")
    else:
        # Raw/original subject folder. Force canonical BIDS ID if mapping exists.
        mapped = _lookup_bids_id(
            "subject_ids.csv",
            original_col="subjID",
            bids_col="bids_subjID",
            original_id=current,
        )
        if mapped != "n/a":
            original_subject_id = current
            scan.subject = _norm_subject(mapped)
            logger.info(f"Subject mapped from original to BIDS: {current} -> {scan.subject}")
        else:
            original_subject_id = current
            logger.warning(f"No subject mapping found for {current}; leaving scan.subject unchanged.")

    subject_session_rows = []
    return 0


def SessionEP(scan: BidsSession) -> int:
    global seq_list, seq_index
    global deprecatedSEMC_run_counter, T1w_mag_run_counter, T1w_ph_run_counter
    global PDw_mag_run_counter, PDw_ph_run_counter, MTw_mag_run_counter, MTw_ph_run_counter
    global MP2RAGE_run_counter, AFI_stx_run_counter, AFI_ptx_run_counter, anat_nm_run_counter
    global tfl_multiMTC_MT_ON_counter, tfl_multiMTC_MT_OFF_counter
    global smap_T1w_counter, smap_PDw_counter, smap_MTw_counter, fallback_smap_counter
    global head_coil_smap_counter, body_coil_smap_counter
    global session_has_loraks, session_detected_shim_attr
    global original_session_id, current_session_row, session_info_done

    # Session mapping filenames have existed in two conventions:
    #   007_sessions.csv
    #   sub-007_sessions.csv
    # Try both.
    clean_sub = str(scan.subject).replace("sub-", "")
    current_ses = str(scan.session)

    if _is_bids_like_session(current_ses):
        # Already prepared/BIDS-like, e.g. ses-02 or 02.
        scan.session = _norm_session(current_ses)
        original_session_id = _lookup_original_id(
            f"{clean_sub}_sessions.csv",
            original_col="sesID",
            bids_col="bids_sesID",
            bids_id=scan.session,
        )
        if original_session_id == "n/a":
            original_session_id = _lookup_original_id(
                f"sub-{clean_sub}_sessions.csv",
                original_col="sesID",
                bids_col="bids_sesID",
                bids_id=scan.session,
            )
        logger.info(f"Session already BIDS-like: {current_ses} -> {scan.session}; original={original_session_id}")
    else:
        # Raw/original session folder, e.g. 20260417. Force canonical BIDS session.
        mapped = _lookup_bids_id(
            f"{clean_sub}_sessions.csv",
            original_col="sesID",
            bids_col="bids_sesID",
            original_id=current_ses,
        )
        if mapped == "n/a":
            mapped = _lookup_bids_id(
                f"sub-{clean_sub}_sessions.csv",
                original_col="sesID",
                bids_col="bids_sesID",
                original_id=current_ses,
            )

        if mapped != "n/a":
            original_session_id = current_ses
            scan.session = _norm_session(mapped)
            logger.info(f"Session mapped from original to BIDS: {current_ses} -> {scan.session}")
        else:
            original_session_id = current_ses
            logger.warning(f"No session mapping found for {current_ses}; leaving scan.session unchanged.")

    current_session_row = _new_session_row(scan)
    session_info_done = False

    session_dir = os.path.join(scan.in_path, "MRI")
    if os.path.isdir(session_dir):
        seq_list = sorted(os.listdir(session_dir))
        seq_list = [s.split("-", 1)[1] if "-" in s else s for s in seq_list]
    else:
        logger.warning(f"MRI session directory not found: {session_dir}")
        seq_list = []
    seq_index = -1

    deprecatedSEMC_run_counter = 0
    T1w_mag_run_counter = 0
    T1w_ph_run_counter = 0
    PDw_mag_run_counter = 0
    PDw_ph_run_counter = 0
    MTw_mag_run_counter = 0
    MTw_ph_run_counter = 0
    MP2RAGE_run_counter = 0
    AFI_stx_run_counter = 0
    AFI_ptx_run_counter = 0
    anat_nm_run_counter = 0
    tfl_multiMTC_MT_ON_counter = 0
    tfl_multiMTC_MT_OFF_counter = 0
    smap_T1w_counter = None
    smap_PDw_counter = None
    smap_MTw_counter = None
    fallback_smap_counter = None
    head_coil_smap_counter = None
    body_coil_smap_counter = None
    session_has_loraks = False
    session_detected_shim_attr = None
    return 0


def SequenceEP(recording: object) -> int:
    global seq_index, session_shim_current_relevant_sequences_counter

    recording.custom["IntendedFor"] = ""
    seq_index += 1
    rec_id = recording.recId()
    if 0 <= seq_index < len(seq_list):
        folder_rec_id = seq_list[seq_index]
        if folder_rec_id != rec_id:
            logger.warning("{}: Id mismatch folder {}".format(recording.recIdentity(False), folder_rec_id))
    else:
        logger.warning(f"Sequence index {seq_index} out of range for sequence list in {recording.recIdentity(False)}")

    if recording.Module() != "MRI":
        return 0

    # Fill the final sub-XXX_sessions.tsv row once from actual bidsification metadata.
    _fill_session_row_once(recording)

    _set_afi_fields(recording, rec_id)

    image_type = _normalise_image_type(_get_attr(recording, "ImageType"))
    _set_gradient_correction_fields(recording, image_type)
    _increment_run_counters(recording, rec_id, image_type)
    _handle_smap_sequence(recording, rec_id)
    _handle_b1_maps(recording, rec_id)

    if rec_id.startswith(tuple(shim_current_relevant_recIDs)):
        session_shim_current_relevant_sequences_counter += 1

    return 0


def RecordingEP(recording: object) -> int:
    global session_shim_currents, session_shim_current_warning_counter, session_detected_shim_attr

    if recording.Module() != "MRI":
        return 0

    rec_id = recording.recId()

    if _is_loraks_recording(recording):
        _handle_loraks_recording(recording)
    else:
        _set_partial_fourier_and_parallel(recording)

    # Re-run AFI logic at recording level as EchoNumber may be recording-specific.
    _set_afi_fields(recording, rec_id)

    if not bidsmap_step and rec_id.startswith(tuple(shim_current_relevant_recIDs)):
        shim_attr, shim_currents = _detect_shim_attribute(recording)
        if shim_attr is None:
            return 0
        if session_detected_shim_attr is None:
            session_detected_shim_attr = shim_attr
            logger.info(f"Detected shim-current metadata field: {shim_attr}")
        elif session_detected_shim_attr != shim_attr:
            logger.warning(
                f"Shim-current metadata field changed within session: {session_detected_shim_attr} -> {shim_attr}"
            )

        if session_shim_currents is None:
            session_shim_currents = shim_currents
        elif session_shim_currents != shim_currents:
            logger.warning(
                f"""Shim currents vary in
                {recording.currentFile(False)}
                from the rest of the session.
                This may render the data unusable!
                {session_shim_currents} vs. {shim_currents}"""
            )
            session_shim_current_warning_counter += 1

    return 0


def FileEP(path: str, recording: object) -> int:
    return 0


def SequenceEndEP(path: str, recording: object) -> int:
    return 0


def SessionEndEP(scan: BidsSession) -> int:
    global session_shim_currents, session_shim_current_warning_counter, session_shim_current_relevant_sequences_counter
    global tfl_multiMTC_MT_ON_counter, tfl_multiMTC_MT_OFF_counter
    global current_session_row, subject_session_rows

    session_path = Path(bids_dir) / _bids_label("sub", scan.subject) / _bids_label("ses", scan.session)
    session_path.mkdir(parents=True, exist_ok=True)

    if not bidsmap_step:
        # If this is LORAKS output, copy existing shim warning files from the corresponding original BIDS dataset.
        copied_warning = False
        if session_has_loraks:
            for fname in (shim_incons_filename, shim_noinfo_filename):
                src = Path(corresponding_bids_data_path) / scan.subject / scan.session / fname
                dst = session_path / fname
                if src.is_file() and not dst.exists():
                    shutil.copyfile(src, dst)
                    copied_warning = True
                    logger.info(f"Copied {fname} from corresponding BIDS dataset")

        # For normal data, create warning files based on detected shim consistency.
        if not session_has_loraks or not copied_warning:
            if session_shim_current_relevant_sequences_counter in (0, 1):
                logger.warning(f"No information on shim current consistency available in {scan.subject} {scan.session}.")
                noinfo_shim_file = session_path / shim_noinfo_filename
                if not noinfo_shim_file.exists():
                    with open(noinfo_shim_file, "w") as f:
                        f.write(
                            f"""WARNING:
There is no information on shim current consistency available in {scan.subject} {scan.session} due to missing sequence data.
(probably no DICOM data for T1w, PDw, and MTw acquisitions)
"""
                        )
            elif session_shim_current_warning_counter == 0:
                print(f"No shim current inconsistencies present in {scan.subject} {scan.session}!")
            else:
                logger.warning(f"Shim current inconsistencies found in {scan.subject} {scan.session}! This may render the data unusable!")
                inconsistency_file = session_path / shim_incons_filename
                if not inconsistency_file.exists():
                    with open(inconsistency_file, "w") as f:
                        f.write(
                            f"""WARNING:
Shim currents are inconsistent for T1w, PDw, MTw, and AFI in {scan.subject} {scan.session}.
This may render the data unusable!
"""
                        )

    # Store the same shim-current summary in the final sessions.tsv row.
    if current_session_row is not None and "shim_curr_cons" in current_session_row:
        if session_shim_current_relevant_sequences_counter in (0, 1) or session_shim_currents is None:
            current_session_row["shim_curr_cons"] = "n/a"
        elif session_shim_current_warning_counter == 0:
            current_session_row["shim_curr_cons"] = "consistent"
        else:
            current_session_row["shim_curr_cons"] = "inconsistent"

    if current_session_row is not None:
        subject_session_rows.append(current_session_row)
        current_session_row = None

    # reset session state
    session_shim_currents = None
    session_shim_current_warning_counter = 0
    session_shim_current_relevant_sequences_counter = 0
    tfl_multiMTC_MT_ON_counter = 0
    tfl_multiMTC_MT_OFF_counter = 0
    return 0


def SubjectEndEP(scan: BidsSession) -> int:
    if not bidsmap_step and not dry_run:
        # Write/merge the sessions.tsv rows generated during bidsification.
        _write_subject_sessions_tsv(scan)

        # Also preserve the old behavior: if prepared input already contains
        # subject-level metadata files, merge/copy them safely as well.
        _copy_or_merge_subject_metadata(scan)
    return 0


def FinaliseEP() -> int:
    if not dry_run:
        _copy_temp_id_maps_to_final()
    return 0
