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
from bidsme.plugins import exceptions
from bidsme.bidsMeta import BidsSession
import pandas as pd
import numpy as np
import os
import re
import warnings
import shutil
import plugin_helper_functions as helper

# Will integrate plugin into logging
import logging

logger = logging.getLogger(__name__)

# code_path = os.path.dirname(__file__)
# base_path = os.path.join(code_path, "..")

# global variables
prep_dir = ""
bids_dir = ""
dry_run = False
tfl_multiMTC_MT_ON_counter = 0
tfl_multiMTC_MT_OFF_counter = 0

shim_current_relevant_recIDs = ["t1w_kp_mtflash3d_v1s", 
                                "pdw_kp_mtflash3d_v1s", 
                                "mtw_kp_mtflash3d_v1s", 
                                "kp_afib1_v1f_4mm_PA", 
                                "kp_afib1_v1g_4mm_PA"]
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


    if recording.Module() == "MRI":

        ### tfl_multiMTC
        if rec_id.startswith("tfl_multiMTC"): 
            if "mt_on" in rec_id.casefold() or "mton" in rec_id.casefold():
                global tfl_multiMTC_MT_ON_counter
                tfl_multiMTC_MT_ON_counter += 1
                recording.custom["tfl_multiMTC_MT_ON_counter"] = tfl_multiMTC_MT_ON_counter
        
            if "mt_off" in rec_id.casefold() or "mtoff" in rec_id.casefold():
                global tfl_multiMTC_MT_OFF_counter
                tfl_multiMTC_MT_OFF_counter += 1
                recording.custom["tfl_multiMTC_MT_OFF_counter"] = tfl_multiMTC_MT_OFF_counter

        ### count how many shim current relevant sequences are in the session
        if rec_id.startswith(tuple(shim_current_relevant_recIDs)):  # startswith() checks against each element of the tuple
            global session_shim_current_relevant_sequences_counter
            session_shim_current_relevant_sequences_counter += 1


        ### t1_mp2rage_sag_p3
        if rec_id.startswith("t1_mp2rage_sag_p3"):
            if "INV1".casefold() in rec_id.casefold():
                recording.custom["inversion_number"] = "1"
            if "INV2".casefold() in rec_id.casefold():
                recording.custom["inversion_number"] = "2"
            # differentiate between two UNI T1 images
            if "UNI_Images".casefold() in rec_id.casefold():
                recording.custom["UniT1_descr"] = "IMG"
            if "UNI-DEN".casefold() in rec_id.casefold():
                recording.custom["UniT1_descr"] = "DEN"


        ### for sensitivity maps (RB1COR): check receive coil and which acquisition it is intended for
        if rec_id.startswith("smap_kp_mtflash3d"):
            receive_coil = recording.getAttribute("ReceiveCoilName")
            if "head" in receive_coil.casefold():
                recording.custom["ReceiveCoil"] = "head"
            elif "body" in receive_coil.casefold():
                recording.custom["ReceiveCoil"] = "body"
            else:
                recording.custom["ReceiveCoil"] = "unknown"
        

            smap_modality = helper.find_smap_modality(seq_list, seq_index)
            if smap_modality:
                recording.custom["IntendedFor"] = smap_modality
            else:
                logger.warning("{}: Unable to determine modality of sensitivity map"
                        .format(recording.recIdentity()))
                recording.custom["IntendedFor"] = "invalid"


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
    ### adapted from Nikita Beliy's plugin
    rec_id = recording.recId()
    if recording.Module() == "MRI":

        ### AFIB1 repetition times
        if rec_id.startswith("kp_afib1_v1g"):       ## for dcm2niix
            tr_index = recording.getAttribute("EchoNumber")

            recording.custom["tr_index"] = tr_index

            tr_list = [0.025,0.125] # in s

            recording.custom["RepetitionTime"] = tr_list[tr_index - 1]


        try:
            # only for dcm2niix, stored as list
            image_type = recording.getAttribute("ImageTypeText")
        except:
            # for hMRI toolbox DICOM import, stored as string like "ORIGINAL\\PRIMARY\\M\\ND "
            image_type = recording.getAttribute("ImageType")
            image_type = [item.strip() for item in image_type.split('\\')]
        finally:
            if "ND" in image_type:
                recording.custom["NonlinearGradientCorrection"] = False
                recording.custom["acq_suffix"] = "-ND"
            else:
                recording.custom["NonlinearGradientCorrection"] = True
                recording.custom["acq_suffix"] = ""
            
            if "M" in image_type:
                recording.custom["part"] = "mag"
            if "P" in image_type:
                recording.custom["part"] = "phase"


        ### check that the shim currents are the same for all T1w, PDw, MTw, and (pTx) AFI scans
        global session_shim_currents
        global session_shim_current_warning_counter

        if rec_id.startswith(tuple(shim_current_relevant_recIDs)):  # startswith() checks against each element of the tuple
            ShimCurrAttr = "ShimSetting"
            shim_currents = recording.getAttribute(ShimCurrAttr)
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


    ## warn if shim currents are inconsistent + delete the bidsified data or create warning file for the corresponding session
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
                        Shim currents are inconsistent for T1w, PDw, MTw, and (pTx) AFI in {scan.subject} {scan.session}. 
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
