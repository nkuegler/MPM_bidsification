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
corresponding_bids_data_path = ""
available_contrasts_loraks = ["t1w_kp_mtflash3d", "pdw_kp_mtflash3d", "mtw_kp_mtflash3d"]
shim_incons_filename = "WARNING_INCONS_SHIMCURR.txt"
shim_noinfo_filename = "WARNING_NOINFO_SHIMCURR.txt"


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

    global corresponding_bids_data_path
    corresponding_bids_data_path = os.path.abspath(os.path.join(bids_dir, '..', '..')) # works for: bids_dir/derivatives/LORAKS

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


    return 0


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

    def get_series_id(str_to_check, recording):

        full_string = recording.currentFile(True)
        if "_0p6" in full_string: # resolution of T1w, PDw, and MTw
            string_end = "_0p6"
        elif "_0p5_sag" in full_string: # resolution of Ernst acquisition
            string_end = "_0p5_sag"
        else:
            logger.warning(f"ProtocolName couldn't be derived properly from {full_string}")
            return str_to_check

        pattern = f"({re.escape(str_to_check)}.*?{re.escape(string_end)})"
        match = re.search(pattern, full_string)
        if match:
            return match.group(1) # correct series id
        else:
            logger.warning(f"ProtocolName couldn't be derived properly from {full_string}")
            return str_to_check


    if recording.Module() == "MRI":

        ### loraks attributes
        if "rec-loraks".casefold() in recording.currentFile(True).casefold():

            ### recon method
            recon_method = "loraks"
            rsos = 0
            if "rec-loraksRsos".casefold() in recording.currentFile(True).casefold():
                recon_method = "loraksRsos"
                rsos = 1
            recording.custom["ReconMethod"] = recon_method
            
            
            ## magnitude or phase
            if recording.getAttribute("Units") == "rad":
                if "phase" in recording.currentFile(True).casefold() \
                        or "ph" in recording.currentFile(True).casefold():   ## double check
                    recording.custom["part"] = "phase"
            else:
                recording.custom["part"] = "mag"

            ## retrieve echo number from filename
            echo_number = re.findall(r'echo-\d+', recording.currentFile(True).casefold())
            if echo_number:
                recording.custom["EchoNumbers"] = f"{int(echo_number[0].split("-")[1]):02d}"
            else:
                logger.error(f"No echo number found in filename: {recording.currentFile(True)}")


            ### set protocol name as attribute
            for ind, contrast_fname in enumerate(available_contrasts_loraks):
                if contrast_fname.casefold() in recording.currentFile(True).casefold():
                    recording.series_id = f"{get_series_id(contrast_fname, recording)}_{recon_method}"
                    recording.series_no = int(np.arange(1, len(available_contrasts_loraks*2), 2)[ind] + rsos) # first element in list = 1+rsos, second = 3+rsos, third = 5+rsos
                    recording.setAttribute("ProtocolName", f"{get_series_id(contrast_fname, recording)}")


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
    
    ## copy SHIM_CURR_INCONSISTENCY warning file to session directory if present in the bidsified data
    shim_incons_file = os.path.join(corresponding_bids_data_path, scan.subject, scan.session, shim_incons_filename)
    if os.path.isfile(shim_incons_file):
        shutil.copy(shim_incons_file, os.path.join(bids_dir, scan.subject, scan.session, shim_incons_filename))
        logger.info(f"Copying {shim_incons_filename} from correponding session in the bidsified dataset")
        
    ## copy SHIM_CURR_NOINFO warning file to session directory if present in the bidsified data
    shim_noinfo_file = os.path.join(corresponding_bids_data_path, scan.subject, scan.session, shim_noinfo_filename)
    if os.path.isfile(shim_noinfo_file):
        shutil.copy(shim_noinfo_file, os.path.join(bids_dir, scan.subject, scan.session, shim_noinfo_filename))
        logger.info(f"Copying {shim_noinfo_filename} from correponding session in the bidsified dataset")
    

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

    return 0

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
