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
import os
import re
import warnings

# Will integrate plugin into logging
import logging
logger = logging.getLogger(__name__)

# global variables
rawfolder = ""
bidsfolder = ""
dry_run = False
id_files_dir = f"id_info"

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
    global rawfolder
    global bidsfolder
    global dry_run
    rawfolder = source
    bidsfolder = destination
    dry_run = dry
    global id_files_dir

    if not os.path.exists(id_files_dir):
        os.makedirs(id_files_dir)

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


    csv_sub_file = f"{id_files_dir}/subject_ids.csv"

    if not os.path.isfile(csv_sub_file):
        subIDs_dict = {'subjID': [], 
                'bids_subjID': []
                }
        sub_id_df = pd.DataFrame(subIDs_dict)
    else:
        sub_id_df = pd.read_csv(csv_sub_file).astype(str)

    global current_subjectID
    current_subjectID = scan.subject

    if scan.subject in sub_id_df['subjID'].values:
        scan.subject = sub_id_df.loc[sub_id_df['subjID'] == scan.subject, 'bids_subjID'].iloc[0]
    else:
        print(f"Subject ID not present in '{csv_sub_file}'. Adding and indexing the subject.")
        if sub_id_df.empty:
            current_bids_subjID = '1'
        else:
            # current_bids_subjID = int(ID_DIR['bids_subjID'].iloc[-1]) + 1
            current_bids_subjID = int(sub_id_df['bids_subjID'].iat[-1]) + 1
        print(f"Current subject: {current_subjectID} -> {current_bids_subjID}")

        new_row = pd.DataFrame({'subjID': [scan.subject], 'bids_subjID': [str(current_bids_subjID)]})
        # display(new_row)
        sub_id_df = pd.concat([sub_id_df, new_row], ignore_index=True)
        
        scan.subject = new_row['bids_subjID'].iloc[0]

    # display(sub_id_df)

    sub_id_df.to_csv(csv_sub_file, index=False)

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
    csv_ses_file = f"{id_files_dir}/{scan.subject}_sessions.csv"

    if not os.path.isfile(csv_ses_file):
        sesIDs_dict = {'sesID': [],
                    'bids_sesID': []
                    }
        ses_id_df = pd.DataFrame(sesIDs_dict)
    else:
        ses_id_df = pd.read_csv(csv_ses_file).astype(str)

    global current_sessionID
    current_sessionID = scan.session

    if scan.session in ses_id_df['sesID'].values:
        scan.session = ses_id_df.loc[ses_id_df['sesID'] == scan.session, 'bids_subjID'].iloc[0]
    else: 
        print(f"Session ID not present in '{csv_ses_file}'. Adding and indexing the subject.")
        if ses_id_df.empty:
            current_bids_sesID = '1'
        else:
            current_bids_sesID = int(ses_id_df['bids_subjID'].iat[-1]) + 1
        print(f"Current session: {current_sessionID} -> {current_bids_sesID}")

        new_row = pd.DataFrame({'sesID': [scan.session], 'bids_subjID': [str(current_bids_sesID)]})
        # display(new_row)
        ses_id_df = pd.concat([ses_id_df, new_row], ignore_index=True)

        scan.session = new_row['bids_subjID'].iloc[0]

    # display(ses_id_df)

    ses_id_df.to_csv(csv_ses_file, index=False)

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
    return 0


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
    
    # Run the find command to search for bvec and bval files in the source directory of the current subject and session
    bval_file_source = os.popen(f"find {rawfolder}/{current_subjectID}/{current_sessionID} -name '*.bval'").read().strip()
    bvec_file_source = os.popen(f"find {rawfolder}/{current_subjectID}/{current_sessionID} -name '*.bvec'").read().strip()
    
    if bval_file_source and bvec_file_source:

        # Extract the filenames without their extensions
        bval_filename, _ = os.path.splitext(os.path.basename(bval_file_source))
        bvec_filename, _ = os.path.splitext(os.path.basename(bvec_file_source))
        
        if bval_filename == bvec_filename:
            bval_path_source = os.path.dirname(bval_file_source)
            print(f"Found matching bval and bvec files in {bval_path_source}.")

            # Extract the file's parent folder from the full path
            bval_folder_source = os.path.basename(bval_path_source)

            # Use regular expression to find the 4-digit number at the end of the folder name
            match = re.search(r'(\d{4})$', bval_folder_source)
            if match:
                sequence_number_4digit = match.group(1) # 4-digit number (as in source data)
                sequence_number_3digit = sequence_number_4digit[1:] # 3-digit number (as in prepared data)

            # Run the find command to search for the according files in the prepared data
            files_avail_prepared = os.popen(f"find {bidsfolder}/{scan.subject}/{scan.session} -name '*{bvec_filename}*'").read().strip()
            
            # The output will have multiple lines. 
            # Split the output into lines and search for the first line that contains the three-digit number
            output_paths = files_avail_prepared.split('\n')
            correct_path = None
            for p in output_paths:
                if sequence_number_3digit in p:
                    correct_path = p
                    break

            if correct_path:
                bval_path_prepared = os.path.dirname(correct_path)
            else:
                warnings.warn(f"No matching line found containing the sequence number {sequence_number_3digit}. Please copy the bvec and bval files manually.")
            
            print(f"Copying bval and bvec files to {bval_path_prepared}.")
            os.system(f"cp {bval_file_source} {bval_path_prepared}")
            os.system(f"cp {bvec_file_source} {bval_path_prepared}")

        else:
            warnings.warn("The bval and bvec files do not have the same name. Please check manually.")

    else:
        warnings.warn("No bval or bvec files found.")
    
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
