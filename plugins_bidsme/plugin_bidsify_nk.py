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

    ### adapted from Nikita Beliy's plugin
    rec_id = recording.recId()
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
    
    
        ### Partial Fourier logic 
        ### adapted from https://gitlab.gwdg.de/cbs-neurophy/image-reconstruction/-/blob/main/core/MriDataMapVBVDImpl.m

        original_level = logging.getLogger().getEffectiveLevel()
        
        try:
            # Temporarily increase logging level to ERROR to suppress warnings
            # otherwise "Could not parse" warnings are raised every time a jsonNIFTI file is processed
            logging.getLogger().setLevel(logging.ERROR)

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
        
        finally:
            # Restore original logging level
            logging.getLogger().setLevel(original_level)

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

            tr_list = [25,125] # ms

            recording.custom["RepetitionTime"] = tr_list[tr_index - 1]
        
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

    return 0


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
