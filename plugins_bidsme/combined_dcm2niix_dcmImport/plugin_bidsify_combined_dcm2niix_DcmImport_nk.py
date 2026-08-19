###############################################################################
# template.py provides the templates for the plugin functions
###############################################################################
# Copyright (c) 2019-2020, University of Liège
# Author: Nikita Beliy
# Owner: Liege University https://www.uliege.be
# Credits: [Marcel Zwiers]
# Maintainer: Nikita Beliy
# Email: Nikita.Beliy@uliege.be
# Status: developpement
###############################################################################
# This file is part of BIDSme
# BIDSme is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
# eegBidsCreator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with BIDSme.  If not, see <https://www.gnu.org/licenses/>.
##############################################################################


# List of personalized, plugin-related errors
from unittest import case
from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession
import pandas as pd
import numpy as np
import os
import re
import warnings
import shutil
import sys

# Get the absolute path of the parent directory of this script and add it to the system path to include helper functions as module
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
import plugin_helper_functions as helper

# Will integrate plugin into logging
import logging

logger = logging.getLogger(__name__)

# code_path = os.path.dirname(__file__)
# base_path = os.path.join(code_path, "..")


# TODO: define start of different sequence names, which are overwritten by new names, which can be passed to the plugin
sequence_names = {          # must be in lists
    "T1w": ["t1w_kp_mtflash3d"],
    "PDw": ["pdw_kp_mtflash3d"],
    "MTw": ["mtw_kp_mtflash3d"],
    "AFI_sTx": ["kp_afib1_v1g", "kp_afib1_v1g_4mm_PA", "kp_afib1_v1f_4mm_PA"], # also possible to replace this with [kp_afib1_v1g, kp_afib1_v1f]
    "AFI_pTx": ["kp_afib1_v1h1_4mm_PA"],
    "LC_slab": ["tfl_multiMTC", "mni_tfl_MTboost"],
    "MP2RAGE": ["t1_mp2rage_sag", "t1_mp2rage_sag_p3"],
    "MPRAGE": ["MPRAGE_ADNI"],
    "sensitivity_maps": ["smaps_kp_mtflash3d", "sens_maps_kp_mtflash3d", "smap_kp_mtflash3d","rfsens_kp_mtflash3d"],
    "nm-sensitive": ["anat-nm"],
    "deprecatedSEMC": ["JS_mod_semc"],
}

afi_prefixes = (
    sequence_names["AFI_pTx"] +
    sequence_names["AFI_sTx"]
)


# global variables
prep_dir = ""
bids_dir = ""
dry_run = False
tfl_multiMTC_MT_ON_counter = 0
tfl_multiMTC_MT_OFF_counter = 0

shim_current_relevant_recIDs = (
    sequence_names["T1w"] +
    sequence_names["PDw"] +
    sequence_names["MTw"] +
    sequence_names["AFI_sTx"] +
    sequence_names["AFI_pTx"]
)
session_shim_currents = None
session_shim_current_warning_counter = 0
session_shim_current_relevant_sequences_counter = 0

# list of sequences in order of acquisition in current session
seq_list = list()

# The index of current sequence, corresponds to order in the sequence list
seq_index = -1

"""
Additional exceptions must derive from corresponding exception class
with changing code between 1 and 9. Code 0 is reserved for generic
function error.
"""


class SubjectMissingError(exceptions.SubjectEPError):
    """
    Raises if subject id isn't found
    """
    code = 1


def InitEP(source: str, destination: str,
           dry: bool,
           **kwargs) -> int:
    """
    This code is run immideatly after loading plugin module
    It means to set-up global variables (like source folder)

    Global switch 'train' is defined to separate if plugin is
    run by bidsmapper or bidscoiner. In train mode several
    tasks non-related to creating the map should be skipped.

    Global switch 'dry' is defined to allow to run in test mode,
    where no actual file modification and writing should be
    performed. Usefull to detect eventual errors.

    'kwargs' is there to allow plugin-specific options passed
    via CLI of CFI

    Parameters
    ----------
    source: str
        path to the source directory where
        all original data files are stored
    destination: str
        path to the output folder, where all
        sorted/bidsified files will be stored
    dry: bool
        switch if it is a dry-run (True) where no modifiyng
        and/or creating of files occures, or nomal (False)
    kwargs:
        unspecified global parameters needed by plugin

    Returns
    -------
    int or None
        return code, if 0 (or None) Initialisation is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.InitEPerror
        code 100
    """
    global prep_dir
    global bids_dir
    global dry_run
    prep_dir = source
    bids_dir = destination
    dry_run = dry

    global bidsmap_step
    bidsmap_step = kwargs.get("bidsmap_step", False) # get the value from the options passed to the plugin, default is False
    bidsmap_step = helper.argument_to_bool(bidsmap_step)
    if bidsmap_step == -1:
        raise exceptions.InitEPError(f"Invalid value for 'bidsmap_step' in plugin options")

    print("options passed to plugin:")
    print(f"- bidsmap_step: {bidsmap_step}, {type(bidsmap_step)}")

    return 0


def SubjectEP(scan: BidsSession) -> int:
    """
    This function is called after entering directory of subjects
    and meant to perform subject-global actions, like extracting
    external data for given subject.

    The default (folder-defined) subject name can be modified
    by modifying 'subject' attribute in the passed BidsSession.
    The sub- prefix is optional for the modifyed subject, and
    will be added afterwards.

    Parameters
    ----------
    scan: BisdSession
        contains session-related information

    Returns
    -------
    int or None
        return code, if 0 (or None) SubjectEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.SubjectEPerror
        code 120
    """

    return 0

def SessionEP(scan: BidsSession) -> int:
    """
    This function is called after entering directory of session
    and meant to adapt session name.

    The default (folder-defined) session name can be modified
    by modifying 'session' field in the passed dictionary.
    The ses- prefix is optional for the modifyed subject

    Parameters
    ----------
    scan: BisdSession

    Returns
    -------
    int or None
        return code, if 0 (or None) SessionEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.SessionEPerror
        code 130
    """

    global seq_list
    global seq_index
    
    session_dir = os.path.join(scan.in_path, "MRI")
    seq_list = sorted(os.listdir(session_dir))
    seq_list = [s.split("-", 1)[1] for s in seq_list]
    seq_index = -1
    # print(f"files in {session_dir}: {seq_list}")

    global deprecatedSEMC_run_counter
    deprecatedSEMC_run_counter = 0

    global T1w_mag_run_counter
    T1w_mag_run_counter = 0
    global T1w_ph_run_counter
    T1w_ph_run_counter = 0

    global PDw_mag_run_counter
    PDw_mag_run_counter = 0
    global PDw_ph_run_counter
    PDw_ph_run_counter = 0

    global MTw_mag_run_counter
    MTw_mag_run_counter = 0
    global MTw_ph_run_counter
    MTw_ph_run_counter = 0

    global MP2RAGE_run_counter
    MP2RAGE_run_counter = 0

    global AFI_stx_run_counter
    AFI_stx_run_counter = 0

    global AFI_ptx_run_counter
    AFI_ptx_run_counter = 0

    global smap_T1w_counter
    smap_T1w_counter = None
    global smap_PDw_counter
    smap_PDw_counter = None
    global smap_MTw_counter
    smap_MTw_counter = None
    global fallback_smap_counter
    fallback_smap_counter = None
    global head_coil_smap_counter
    head_coil_smap_counter = None
    global body_coil_smap_counter
    body_coil_smap_counter = None

    global anat_nm_run_counter
    anat_nm_run_counter = 0

    return 0

def SequenceEP(recording: object) -> int:
    """
    This function is called after loading first file of
    a sequence and meant to perform sequence-global actions,
    like checking sequence order and validity.

    Custom recording-global variables can be defined here.

    Parameters
    ----------
    recording: Modules.base.baseModule
        A recording with loaded first file

    Returns
    -------
    int or None
        return code, if 0 (or None) SequenceEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.SequenceEPerror
        code 140
    """

    global seq_index

    recording.custom["IntendedFor"] = ""
    seq_index += 1
    rec_id = seq_list[seq_index]

    # checking if current sequence corresponds in correct place in list
    if rec_id != recording.recId():
        logger.warning("{}: Id mismatch folder {}"
                       .format(recording.recIdentity(False),
                               rec_id))


    ### adapted from Nikita Beliy's plugin
    if recording.Module() == "MRI":

        ### ------------------- AFI parameters -------------------
        ### Purpose: extract AFI repetition times and SpoilingRFPhaseIncrement for AFIB1 sequences directly from the SPM DICOM-imported data (not possible with dcm2niix-converted data)

        if rec_id.startswith(tuple(afi_prefixes)):

            with helper.temporary_logging_level(logging.ERROR):
                DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")

            if DcmImportCheck is None: # check if the attribute exists. If it doesn't exists, the query will follow dcm2niix convention. Otherwise it will fall back to SPM DICOM import convention.

                ### for dcm2niix-converted data
                pass # recording-specific TR definition performed in RecordingEP()

            else:
                ### for SPM DICOM-imported data
                ### AFIB1 repetition times
                alTR = "CSASeriesHeaderInfo/MrPhoenixProtocol/alTR"
                alTR = recording.getAttribute(alTR)
                recording.custom["alTR"] = alTR
                recording.custom["alTR_sorted"] = sorted(alTR)
                
                ### AFIB1 SpoilingRFPhaseIncrement
                adFree = "CSASeriesHeaderInfo/MrPhoenixProtocol/sWipMemBlock/adFree"
                adFree = recording.getAttribute(adFree)
                # Ensure adFree is a list; if not, convert it to a list
                if not isinstance(adFree, list):
                    try:
                        adFree = list(adFree)
                    except TypeError:
                        adFree = [adFree]
                recording.custom["SpoilingRFPhaseIncrement"] = adFree[6] if len(adFree) > 6 else "n/a"

            del DcmImportCheck

        ### ------------------- LC slab parameters -------------------
        ### Purpose: extract information about the LC slab acquisition (tfl_multiMTC, mni_tfl_MTboost) from the SPM DICOM-imported data (not possible with dcm2niix-converted data)

        if rec_id.startswith(tuple(sequence_names["LC_slab"])): 

            print(f"rec_id: {rec_id}")
            global tfl_multiMTC_MT_ON_counter
            global tfl_multiMTC_MT_OFF_counter

            with helper.temporary_logging_level(logging.ERROR):
                DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")

            if DcmImportCheck is None: # check if the attribute exists. If it doesn't exists, the query will follow dcm2niix convention. Otherwise it will fall back to SPM DICOM import convention.

                ### for dcm2niix-converted data
                mt_state = recording.getAttribute("MTState")

                if mt_state is not None: # attribute must be available
                    logger.info(f"MTState: {mt_state}")

                    if mt_state:
                        # counter for MT ON sequences
                        tfl_multiMTC_MT_ON_counter += 1
                        recording.custom["tfl_multiMTC_MT_ON_counter"] = tfl_multiMTC_MT_ON_counter

                        mtc_amplitude = "n/a" # cannot be extracted from dcm2niix-converted json
                        recording.custom["mtc_amplitude"] = mtc_amplitude
                        recording.custom["mtc_amplitude_int"] = None # integer value of volts
                    else: 
                        # counter for MT OFF sequences
                        tfl_multiMTC_MT_OFF_counter += 1
                        recording.custom["tfl_multiMTC_MT_OFF_counter"] = tfl_multiMTC_MT_OFF_counter


            else: 
                ### for SPM DICOM-imported data

                if recording.getattribute("CSASeriesHeaderInfo/MrPhoenixProtocol/sPrepPulses/ucMTC"): # check if the attribute exists. If there is no MT preparation pulse, ucMT does not exist (None). 

                    # counter for MT ON sequences
                    tfl_multiMTC_MT_ON_counter += 1
                    recording.custom["tfl_multiMTC_MT_ON_counter"] = tfl_multiMTC_MT_ON_counter

                    # Extract voltage of the MT pulse
                    rf_pulses = recording.getAttribute("CSASeriesHeaderInfo/MrPhoenixProtocol/sTXSPEC/aRFPULSE")
                    # Find the sMTC_RF or sSRFMTC pulse and extract flAmplitude
                    # careful: this field also exists in all MPM measurements, but the MT preparation pulse is only scheduled in MT sequences (MTw and multiMTC). 
                    mtc_amplitude = None
                    for pulse in rf_pulses:
                        if pulse.get('tName') in {'sMTC_RF', 'sSRFMTC', 'SRFExcit'}:
                            mtc_amplitude = pulse.get('flAmplitude')    
                            break
                    if not mtc_amplitude:
                        mtc_amplitude = 0
                    recording.custom["mtc_amplitude"] = round(mtc_amplitude, 3)
                    recording.custom["mtc_amplitude_int"] = f"{int(mtc_amplitude)}V" # integer value of volts

                else: 
                    # counter for MT OFF sequences
                    tfl_multiMTC_MT_OFF_counter += 1
                    recording.custom["tfl_multiMTC_MT_OFF_counter"] = tfl_multiMTC_MT_OFF_counter

            del DcmImportCheck

        ### ------------------- MT preparation pulse parameters -------------------
        ### can be adapted to other sequences with MT preparation pulses, e.g. LC slab acquisition (tfl_multiMTC)

        if rec_id.startswith(tuple((sequence_names["MTw"] + sequence_names["LC_slab"]))):
            with helper.temporary_logging_level(logging.ERROR):
                DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")
            if DcmImportCheck is not None: # check if the attribute exists. The following information is only avalable in SPM DICOM import json files.

                ### MTpulse: sWipMemBlock/adFree[0] = flip angle, sWipMemBlock/adFree[1] = Offset in Hz, sWipMemBlock/alFree[0] = pulse duration in us, rf spoiling increment (level1; level2) = sWipMemBlock/adFree[2]; sWipMemBlock/adFree[3] (in degrees)

                MTpulseInfo_adFree = recording.getAttribute("CSASeriesHeaderInfo/MrPhoenixProtocol/sWipMemBlock/adFree") # MT pulse details, floating point values
                MTpulseInfo_alFree = recording.getAttribute("CSASeriesHeaderInfo/MrPhoenixProtocol/sWipMemBlock/alFree") # MT pulse details, integer values

                recording.custom["MTpulse_FlipAngle"] = MTpulseInfo_adFree[0] # in degrees
                recording.custom["MTpulse_Offset"] = MTpulseInfo_adFree[1] # in Hz
                recording.custom["RFspoiling_increment_lvl1"] = MTpulseInfo_adFree[2] # in degrees
                recording.custom["RFspoiling_increment_lvl2"] = MTpulseInfo_adFree[3] # in degrees
                recording.custom["MTpulse_Duration"] = MTpulseInfo_alFree[0] # in us
                
            del DcmImportCheck

        ### ------------------- Deprecated MESE sequence -------------------
        ### only for a specific old MESE sequence protocol name 'JS_mod_semc'
        global deprecatedSEMC_run_counter
        if rec_id.startswith(tuple(sequence_names["deprecatedSEMC"])):
            deprecatedSEMC_run_counter += 1
            recording.custom["deprecatedSEMC_run_counter"] = deprecatedSEMC_run_counter


        ### ------------------- Nonlinear Gradient Correction status -------------------
        image_type = recording.getAttribute("ImageTypeText") # in dcm2niix converted data
        if image_type is None:
            image_type = recording.getAttribute("ImageType") # in SPM DICOM import data
        # print(f"image_type type: {type(image_type)}")
        # print(f"image_type: {image_type}")

        if isinstance(image_type, list):
            # conversion_type = dcm2niix, ImageType already stored as list
            sDistortionCorrFilter = np.nan
        elif isinstance(image_type, str):
            # conversion_type= SPM DICOM import, ImageType stored as string like "ORIGINAL\\PRIMARY\\M\\ND"
            image_type = [item.strip() for item in image_type.split("\\")]
            sDistortionCorrFilter = \
                "CSASeriesHeaderInfo/MrPhoenixProtocol/sDistortionCorrFilter/ucMode"
            sDistortionCorrFilter = recording.getAttribute(sDistortionCorrFilter)
        else:
            # image_type is None or an unexpected type
            logger.warning(f"Unexpected ImageType format: {image_type}")
            image_type = []

        match image_type:
            case _ if any(_ in image_type for _ in ["DIS3D", "3D"]):
                DistCorrType = "3D"
            case _ if any(_ in image_type for _ in ["DIS2D", "2D"]):
                DistCorrType = "2D"
            case _:
                DistCorrType = None


        if "ND" in image_type:
            recording.custom["acq_suffix"] = "-ND"
            if any(name.casefold() in rec_id.casefold() 
                   for name in sequence_names["MPRAGE"]):
                ### additional check for MPRAGE_ADNI sequence as this deviates from the usual convention, but only in the ND version
                recording.custom["NonlinearGradientCorrection"] = False
                recording.custom["NonlinearGradientCorrectionType"] = "none"
            else:
                if not DistCorrType and sDistortionCorrFilter in [1, np.nan]:
                    recording.custom["NonlinearGradientCorrection"] = False
                    recording.custom["NonlinearGradientCorrectionType"] = "none"
                else:
                    logger.warning("{}: ImageType 'ND', DistCorrType '{}', and sDistortionCorrFilter value '{}' do not match"
                            .format(recording.recIdentity(), DistCorrType, sDistortionCorrFilter))
                    recording.custom["NonlinearGradientCorrection"] = "n/a"
                    recording.custom["NonlinearGradientCorrectionType"] = "n/a"
        else:
            recording.custom["acq_suffix"] = "" 
            # check for 3D first as in 3D correction both "2D" and "3D" may be found in image_type
            if (sDistortionCorrFilter in [4, np.nan] and DistCorrType == "3D") \
                    or (sDistortionCorrFilter in [2, np.nan] and DistCorrType == "2D"):
                recording.custom["NonlinearGradientCorrection"] = True
                recording.custom["NonlinearGradientCorrectionType"] = DistCorrType
            else:
                logger.warning("{}: ImageType '{}', DistCorrType '{}', and sDistortionCorrFilter value '{}' do not match"
                            .format(recording.recIdentity(), image_type, DistCorrType, sDistortionCorrFilter))
                recording.custom["NonlinearGradientCorrection"] = "n/a"
                recording.custom["NonlinearGradientCorrectionType"] = "n/a"


        ### ------------------- Magnitude/Phase part of the image -------------------
        if "M" in image_type:
            recording.custom["part"] = "mag"     # in SPM DICOM import, also "ComplexImageComponent" available
        if "P" in image_type:
            recording.custom["part"] = "phase"


        ### ------------------- Run counters for various sequences -------------------
        ### 3T data T1w, PDw, MTw run counter
        global T1w_mag_run_counter
        global T1w_ph_run_counter
        global PDw_mag_run_counter
        global PDw_ph_run_counter
        global MTw_mag_run_counter
        global MTw_ph_run_counter
        global MP2RAGE_run_counter
        global AFI_stx_run_counter
        global AFI_ptx_run_counter
        global anat_nm_run_counter

        if rec_id.startswith(tuple(sequence_names["T1w"])):
            if "M" in image_type:
                T1w_mag_run_counter += 1
                recording.custom["T1w_run_counter"] = T1w_mag_run_counter
            if "P" in image_type:
                T1w_ph_run_counter += 1
                recording.custom["T1w_run_counter"] = T1w_ph_run_counter
        elif rec_id.startswith(tuple(sequence_names["PDw"])):
            if "M" in image_type:
                PDw_mag_run_counter += 1
                recording.custom["PDw_run_counter"] = PDw_mag_run_counter
            if "P" in image_type:
                PDw_ph_run_counter += 1
                recording.custom["PDw_run_counter"] = PDw_ph_run_counter
        elif rec_id.startswith(tuple(sequence_names["MTw"])):
            if "M" in image_type:
                MTw_mag_run_counter += 1
                recording.custom["MTw_run_counter"] = MTw_mag_run_counter
            if "P" in image_type:
                MTw_ph_run_counter += 1
                recording.custom["MTw_run_counter"] = MTw_ph_run_counter
        elif rec_id.startswith(tuple(sequence_names["AFI_sTx"])):
            AFI_stx_run_counter += 1
            recording.custom["AFI_stx_run_counter"] = AFI_stx_run_counter
        elif rec_id.startswith(tuple(sequence_names["AFI_pTx"])):
            AFI_ptx_run_counter += 1
            recording.custom["AFI_ptx_run_counter"] = AFI_ptx_run_counter
        elif rec_id.startswith(tuple(sequence_names["MP2RAGE"])):
            MP2RAGE_run_counter += 1
            recording.custom["MP2RAGE_run_counter"] = MP2RAGE_run_counter
        elif rec_id.startswith(tuple(sequence_names["nm-sensitive"])):  # special case
            anat_nm_run_counter += 1
            recording.custom["anat_nm_run_counter"] = anat_nm_run_counter
        else:
            pass

        ### ------------------- Counter for shim current relevant sequences -------------------
        ### count how many shim current relevant sequences are in the session
        if rec_id.startswith(tuple(shim_current_relevant_recIDs)):  # startswith() checks against each element of the tuple
            global session_shim_current_relevant_sequences_counter
            session_shim_current_relevant_sequences_counter += 1


        # ### ------------------- MP2RAGE naming information -------------------
        # ### t1_mp2rage_sag_p3
        # if rec_id.startswith(sequence_names["MP2RAGE"]):
        #     if "INV1".casefold() in rec_id.casefold():
        #         recording.custom["inversion_number"] = "1"
        #     if "INV2".casefold() in rec_id.casefold():
        #         recording.custom["inversion_number"] = "2"
        #     # differentiate between two UNI T1 images
        #     if "UNI_Images".casefold() in rec_id.casefold():
        #         recording.custom["UniT1_descr"] = "IMG"
        #     if "UNI-DEN".casefold() in rec_id.casefold():
        #         recording.custom["UniT1_descr"] = "DEN"


        ### ------------------- Extract information for sensitivity maps -------------------
        ### for sensitivity maps (RB1COR): check receive coil and which acquisition it is intended for
        if rec_id.startswith(tuple(sequence_names["sensitivity_maps"])):
            global smap_T1w_counter
            global smap_PDw_counter
            global smap_MTw_counter
            global fallback_smap_counter
            global head_coil_smap_counter
            global body_coil_smap_counter
            
            # assumptions: 
            # - there are either only head/array sensitivity maps (Terra) or head and body sensitivity maps (Prisma)
            # - rec_id contains "head", it does not contain "array"
            # if these asusmptions are not met, the counters may not be incremented correctly

            with helper.temporary_logging_level(logging.ERROR):
                DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")
            if DcmImportCheck is None: # check if the attribute exists.
                ReceiveCoilName = recording.getAttribute("ReceiveCoilName") # in dcm2niix converted data
            else: 
                # requires intermediate step as the query does not handle nested lists and dictionaries well
                ReceiveCoilNameList = recording.getAttribute("CSASeriesHeaderInfo/MrPhoenixProtocol/sCoilSelectMeas/aRxCoilSelectData") 
                ReceiveCoilName = ReceiveCoilNameList[0]["asList"][0]["sCoilElementID"]["tCoilID"] # in SPM DICOM import 

            if any(name.casefold() in ReceiveCoilName.casefold() for name in ["head", "32ch"]):
                current_ReceiveCoil = "head"
            # elif any(name.casefold() in ReceiveCoilName.casefold() for name in ["array"]):
            #     current_ReceiveCoil = "array"       ## potentially deprecated
            elif any(name.casefold() in ReceiveCoilName.casefold() for name in ["body", "bc"]):
                current_ReceiveCoil = "body"
            else:
                current_ReceiveCoil = "unknown"
                logger.warning("{}: Unknown receive coil name '{}'"
                        .format(recording.recIdentity(), ReceiveCoilName))

            recording.custom["ReceiveCoil"] = current_ReceiveCoil
            
            if current_ReceiveCoil in ["head", "array"]:
                if not head_coil_smap_counter:
                    head_coil_smap_counter = 1
                else:
                    head_coil_smap_counter += 1
            elif current_ReceiveCoil == "body":
                if not body_coil_smap_counter:
                    body_coil_smap_counter = 1
                else:
                    body_coil_smap_counter += 1

            del DcmImportCheck

            ### ------------------- Sensitivity map intended for ------------------- 
            ### find_smap_modality() searches for a matching T1w/PDw/MTw sequence in the session and returns the corresponding modality.
            ### In the Terra.X protocol, the sensitivity maps are acquired after the T1w/PDw/MTw sequences, so the search direction is reversed.
            # 
            with helper.temporary_logging_level(logging.ERROR):
                TerraCheck = recording.getAttribute("ManufacturersModelName")
                PrismaCheck = recording.getAttribute("ManufacturerModelName") # no s

            if TerraCheck and any(name.casefold() in TerraCheck.casefold() for name in ["Terra"]):
                search_direction = "backward"
            elif PrismaCheck and any(name.casefold() in PrismaCheck.casefold() for name in ["Prisma"]):
                search_direction = "forward"
            else:
                logger.warning("{}: Unknown scanner model '{}', defaulting to backward search for sensitivity map intended for modality")
            smap_modality = helper.find_smap_modality(seq_list, seq_index, search_direction=search_direction)
            if smap_modality:
                recording.custom["IntendedFor"] = smap_modality
                if isinstance(head_coil_smap_counter, int) and \
                        isinstance(body_coil_smap_counter, int) and \
                        head_coil_smap_counter != body_coil_smap_counter:
                    # increment the contrast-specific count if head and body coil smaps are available
                    increase_value = 1 
                elif isinstance(head_coil_smap_counter, int) and \
                        not body_coil_smap_counter:
                    # increment the contrast-specific count if only head coil smaps are available
                    increase_value = 1
                elif isinstance(body_coil_smap_counter, int) and \
                        not head_coil_smap_counter:
                    # increment the contrast-specific count if only body coil smaps are available
                    increase_value = 1
                else:
                    increase_value = 0 # do not increment the contrast-specific count

                # each T1w/PDw/MTw smap gets a different run number. 
                # However, sometimes there are head and body smaps for the same T1w/PDw/MTw sequence, so we need to account for that with all the other counters above.
                if smap_modality == "T1w":
                    if not smap_T1w_counter:
                        smap_T1w_counter = 1
                    else:
                        smap_T1w_counter += increase_value
                    recording.custom["smap_run"] = smap_T1w_counter
                elif smap_modality == "PDw":
                    if not smap_PDw_counter:
                        smap_PDw_counter = 1
                    else:
                        smap_PDw_counter += increase_value
                    recording.custom["smap_run"] = smap_PDw_counter
                elif smap_modality == "MTw":
                    if not smap_MTw_counter:
                        smap_MTw_counter = 1
                    else:
                        smap_MTw_counter += increase_value
                    recording.custom["smap_run"] = smap_MTw_counter
                else:
                    raise ValueError(f"Unknown modality returned from helper function: {smap_modality}")

            else:
                if bidsmap_step:
                    logger.info(f"WARNING: {recording.recIdentity()}: Unable to determine modality of sensitivity map")
                else:
                    logger.warning("{}: Unable to determine modality of sensitivity map"
                            .format(recording.recIdentity()))
                recording.custom["IntendedFor"] = "unknown"
                if not fallback_smap_counter:
                    fallback_smap_counter = 1
                else:
                    fallback_smap_counter += 1 
                recording.custom["smap_run"] = fallback_smap_counter


        ### ------------------- Special sequences for B1 mapping --------------------
        ### differernt B1 maps (specific to data from Paris)
        ### Using the rec_id to extract information IS NOT RECOMMENDED! Can only be used to account for very specific cases.

        if rec_id.casefold().startswith("b1map_"):
            if rec_id.casefold().startswith("b1map_3DREAM".casefold()):
                if "RefVolt".casefold() in rec_id.casefold():
                    recording.custom["B1acq"] = "3DREAMrefVolt"
                elif "relB1".casefold() in rec_id.casefold():
                    recording.custom["B1acq"] = "3DREAMrelB1"
                else:
                    recording.custom["B1acq"] = "3DREAM"
            
            if rec_id.casefold().startswith("b1map_product".casefold()):
                recording.custom["B1acq"] = "product"
            
            if rec_id.casefold().startswith("b1map_neurospin".casefold()):
                if "CP".casefold() in rec_id.casefold() and "mode".casefold() in rec_id.casefold():
                    recording.custom["B1acq"] = "neurospin_CPmode"
                elif "VR".casefold() in rec_id.casefold():
                    recording.custom["B1acq"] = "neurospin_VR"
                else: 
                    recording.custom["B1acq"] = "neurospin"


def RecordingEP(recording: object) -> int:
    """
    This function is called after loading each file of
    a sequence and meant to perform actions on recordings,
    like quality checks, and metafields corrections.

    Parameters
    ----------
    recording: Modules.base.baseModule
        A recording with loaded file

    Returns
    -------
    int or None
        return code, if 0 (or None) RecordingEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.RecordingEPerror
        code 150
    """

    ### ------------------- AFI repetition times -------------------

    rec_id = recording.recId()
    if recording.Module() == "MRI":
        if rec_id.startswith(tuple(afi_prefixes)):

            with helper.temporary_logging_level(logging.ERROR):
                DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")
            
            if DcmImportCheck is None: # check if the attribute exists. If it doesn't exists, the query will follow dcm2niix convention. Otherwise it will fall back to SPM DICOM import convention.

                ### for dcm2niix-converted data
                ### AFIB1 repetition times
                tr_index = recording.getAttribute("EchoNumber")
                recording.custom["tr_index"] = tr_index
                tr_list = [0.025,0.125] # in s
                recording.custom["RepetitionTime"] = tr_list[tr_index - 1]
                
            else:
                ### for SPM DICOM-imported data
                index = recording.getAttribute("EchoNumbers")

                TR = recording.custom["alTR"][index - 1]
                # Need to be sure about units!
                recording.custom["RepetitionTime"] = round(TR * 1e-6, 10)

                recording.custom["index"] = index
                recording.custom["tr_index"] = \
                    recording.custom["alTR_sorted"].index(TR) + 1

            del DcmImportCheck


        ### ----------- Partial Fourier Logic & Parallel Acquisition Technique --------------
        ### adapted from https://gitlab.gwdg.de/cbs-neurophy/image-reconstruction/-/blob/main/core/MriDataMapVBVDImpl.m

        with helper.temporary_logging_level(logging.ERROR):
            DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")

        if DcmImportCheck is None: 
            ### for dcm2niix-converted data
            pass # partial fourier and parallel acquisition technique information is already extracted in the dcm2niix conversion and stored in the json file -> can be directly accessed from the bidsmap

        else:
            ### for SPM DICOM-imported data

            ## Partial Fourier
            ucPhasePartialFourier = "CSASeriesHeaderInfo/MrPhoenixProtocol/sKSpace/ucPhasePartialFourier"
            ucPhasePartialFourier = recording.getAttribute(ucPhasePartialFourier)
            if ucPhasePartialFourier == 1: # 4/8
                phasePartialFourier = 0.5
            elif ucPhasePartialFourier == 2: # 5/8
                phasePartialFourier = 0.625
            elif ucPhasePartialFourier == 4: # 6/8
                phasePartialFourier = 0.75
            elif ucPhasePartialFourier == 8: # 7/8
                phasePartialFourier = 0.875
            else:
                phasePartialFourier = 1


            ucSlicePartialFourier = "CSASeriesHeaderInfo/MrPhoenixProtocol/sKSpace/ucSlicePartialFourier"
            ucSlicePartialFourier = recording.getAttribute(ucSlicePartialFourier)
            if ucSlicePartialFourier == 1: # 4/8
                slicePartialFourier = 0.5
            elif ucSlicePartialFourier == 2: # 5/8
                slicePartialFourier = 0.625
            elif ucSlicePartialFourier == 4: # 6/8
                slicePartialFourier = 0.75
            elif ucSlicePartialFourier == 8: # 7/8
                slicePartialFourier = 0.875
            else:
                slicePartialFourier = 1


            recording.custom["PartialFourier"] = slicePartialFourier * phasePartialFourier


            if phasePartialFourier < 1 and slicePartialFourier < 1:
                recording.custom["PartialFourierDirection"] = "COMBINATION"
            elif phasePartialFourier < 1:
                recording.custom["PartialFourierDirection"] = "PHASE"
            elif slicePartialFourier < 1:
                recording.custom["PartialFourierDirection"] = "SLICE_SELECT"
            else:
                recording.custom["PartialFourierDirection"] = ""


            ## Parallel Acquisition Technique
            ucPATMode = "CSASeriesHeaderInfo/MrPhoenixProtocol/sPat/ucPATMode"
            ucPATMode = recording.getAttribute(ucPATMode)

            if ucPATMode == 2:
                recording.custom["ParallelAcquisitionTechnique"] = "GRAPPA"
            elif ucPATMode == 16:
                recording.custom["ParallelAcquisitionTechnique"] = "CAIPIRINHA"
            else:
                recording.custom["ParallelAcquisitionTechnique"] = "n/a"


        ### ------------------- Shim current consistency check -------------------

        if not bidsmap_step:
            ### check that the shim currents are the same for all T1w, PDw, MTw, and AFI scans
            global session_shim_currents
            global session_shim_current_warning_counter
            
            if rec_id.startswith(tuple(shim_current_relevant_recIDs)):  # startswith() checks against each element of the tuple
                with helper.temporary_logging_level(logging.ERROR):
                    DcmImportCheck = recording.getAttribute("CSASeriesHeaderInfo")

                if DcmImportCheck is None: 
                    ShimCurrentAttr = "ShimSetting"
                else:
                    ShimCurrentAttr = "CSASeriesHeaderInfo/MrPhoenixProtocol/sGRADSPEC/alShimCurrent"
                shim_currents = recording.getAttribute(ShimCurrentAttr)
                if session_shim_currents is None:
                    session_shim_currents = shim_currents
                else:
                    if session_shim_currents != shim_currents:
                        logger.warning(f"""Shim currents vary in 
                                    {recording.currentFile(False)} 
                                    from the rest of the session. 
                                    This renders the data useless!
                                    {session_shim_currents} vs. {shim_currents}""")
                        session_shim_current_warning_counter += 1
                del DcmImportCheck


def FileEP(path: str, recording: object) -> int:
    """
    This function is called after copiyng an individual
    recording file to its destination, for example checking
    its integrity or anonimize.

    Parameters
    ----------
    path: str
        path to copied file, garanteed to exist
    recording: Modules.base.baseModule
        A recording with loaded file

    Returns
    -------
    int or None
        return code, if 0 (or None) RecordingEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.FileEPerror
        code 160
    """
    return 0


def SequenceEndEP(path: str, recording: object) -> int:
    """
    This function is called after treating all files from
    given sequence(recording). The currntFile for recording
    is the last file of sequence. It can be used to sequence
    global actions, like numkber of files check and combining.

    Parameters
    ----------
    path:
        path to folder with series of copied files
    recording: Modules.base.baseModule
        A recording with loaded file

    Returns
    -------
    int or None
        return code, if 0 (or None) RecordingEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.SequenceEndEPerror
        code 170
    """
    return 0


def SessionEndEP(scan: BidsSession) -> int:
    """
    This function is called after processing last recording
    of the session and meant to complete session by any
    additional information.

    Parameters
    ----------
    scan: BisdSession

    Raises
    ------
    Error.SessionEndEPerror
        code 180
    """
    global tfl_multiMTC_MT_ON_counter
    global tfl_multiMTC_MT_OFF_counter

    tfl_multiMTC_MT_ON_counter = 0
    tfl_multiMTC_MT_OFF_counter = 0


    if not bidsmap_step:
        ## warn if shim currents are inconsistent + create warning file for the corresponding session
        global session_shim_current_warning_counter
        global session_shim_current_relevant_sequences_counter

        session_path = f"{bids_dir}/{scan.subject}/{scan.session}"

        if session_shim_current_relevant_sequences_counter in (0, 1): 
            logger.warning(f"""No information on shim current consistency available in {scan.subject} {scan.session}.""")
            ## create a txt file indicating that there is no information on shim current consistency
            noinfo_shim_file = os.path.join(session_path, "WARNING_NOINFO_SHIMCURR.txt")
            with open(noinfo_shim_file, "w") as f:
                f.write(f"""WARNING: 
                        There is no information on shim current consistency available in {scan.subject} {scan.session} due to missing sequence data.
                        (probably no DICOM data for T1w, PDw, and MTw acquisitions)
                        
                        """)
        else:
            if session_shim_current_warning_counter == 0:
                print(f"No shim current inconsistencies present in {scan.subject} {scan.session}!")
            else:
                logger.warning(f"""Shim current inconsistencies found in {scan.subject} {scan.session}! This may render the data USELESS!""")

                # ## delete the bidsified data of the corresponding session
                # try:
                #     # List all contents
                #     for item in os.listdir(session_path):
                #         item_path = os.path.join(session_path, item)
                #         if os.path.isfile(item_path):
                #             os.remove(item_path)
                #         elif os.path.isdir(item_path):
                #             shutil.rmtree(item_path)
                # except Exception as e:
                #     print(f"Error while cleaning directory: {e}")

                ## Create a txt file indicating shim current inconsistencies
                inconsistency_file = os.path.join(session_path, "WARNING_INCONS_SHIMCURR.txt")
                with open(inconsistency_file, "w") as f:
                    f.write(f"""WARNING: 
                            Shim currents are inconsistent for T1w, PDw, MTw, and AFI in {scan.subject} {scan.session}. 
                            This may render the data unusable!

                            """)
    

    ## reset shim currents for next session
    global session_shim_currents
    session_shim_currents = None

    ## reset the warning counter for shim currents
    session_shim_current_warning_counter = 0

    ## reset the counter for relevant sequences
    session_shim_current_relevant_sequences_counter = 0


def SubjectEndEP(scan: BidsSession) -> int:
    """
    This function is called after processing last session
    of the subject and meant to perform global subject
    actions, for ex. checking for missing session

    Parameters
    ----------
    scan: BisdSession

    Raises
    ------
    Error.SubjectEndEPerror
        code 180
    """

    if not bidsmap_step:
        ## copy sessions tsv and json files for each subject
        subject_sessions_pattern = f"{scan.subject}_sessions"
        for file_name in os.listdir(scan.in_path):
            if re.match(subject_sessions_pattern, file_name):
                prep_file = os.path.join(scan.in_path, file_name)
                bids_file = os.path.join(f"{bids_dir}/{scan.subject}", file_name)
                shutil.copy(prep_file, bids_file)
                # print(f"Copying {prep_file} to {bids_file}")

def FinaliseEP() -> int:
    """
    This function is called after treating all files from
    the source directory. All global final actions, like
    integrity checks can be performed there.

    Returns
    -------
    int or None
        return code, if 0 (or None) RecordingEP is
        succesful. Non 0 if there some error, where
        code should indicate the problem. The code
        must be in range [0-9]

    Raises
    ------
    Error.FinaliseError
        code 190
    """
    return 0
