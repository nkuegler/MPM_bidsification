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
import json
from datetime import datetime
import shutil
from pathlib import Path

# Will integrate plugin into logging
import logging

logger = logging.getLogger(__name__)

plugin_path = os.path.dirname(__file__)

# global variables
nifti_dir = ""
prep_dir = ""
dry_run = False
id_files_dir_name = f"id_info"
id_files_dir = ""
base_dir = ""
sessions_tsv_template = None 
subN_sessions_dict = {}
ses_dict_populated_for_this_ses = False
data_avail_in_dir = False

shim_current_relevant_recIDs = ["t1w_kp_mtflash3d", 
                                "pdw_kp_mtflash3d", 
                                "mtw_kp_mtflash3d", 
                                "kp_afib1_v1f", 
                                "kp_afib1_v1g"]
session_shim_currents = None
session_shim_current_warning_counter = 0
session_shim_current_relevant_sequences_counter = 0

def remove_trailing_slash(path):
    ## making sure that there is no trailing slash
    return path[:-1] if path.endswith('/') else path

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
    global nifti_dir
    global prep_dir
    global dry_run
    nifti_dir = source
    prep_dir = destination
    dry_run = dry

    global id_files_dir_name
    global id_files_dir

    nifti_dir = remove_trailing_slash(nifti_dir) # to ensure correct functioning of os.path.dirname
    prep_dir = remove_trailing_slash(prep_dir) # to ensure correct functioning of os.path.dirname

    global base_dir
    base_dir = os.path.dirname(nifti_dir)

    id_files_dir = f"{base_dir}/{id_files_dir_name}"

    if not os.path.exists(id_files_dir):
        os.makedirs(id_files_dir)

    global sessions_tsv_template
    sessions_tsv_template = kwargs.get("sessions_tsv_template", None) # get the value from the options passed to the plugin, default is None
    sessions_tsv_template = str(Path(sessions_tsv_template))
    if sessions_tsv_template == None:
        raise exceptions.InitEPError(f"No sessions_tsv_template specified in plugin options")

    print(f"""Loading sessions_nk.json from {sessions_tsv_template}.
          This functionality is not part of Bidsme, but implemented in a plugin. 
          It only works for processing all sessions of a subjects. Problems may 
          arise if the plugin is used for single sessions.""")

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
        sub_id_df = pd.DataFrame(subIDs_dict, dtype=str)
    else:
        sub_id_df = pd.read_csv(csv_sub_file, dtype={'subjID': str, 'bids_subjID': str})

    global current_subjectID
    current_subjectID = scan.subject

    if scan.subject in sub_id_df['subjID'].values:
        scan.subject = f"{int(sub_id_df.loc[sub_id_df['subjID'] == scan.subject, 'bids_subjID'].iloc[0]):03}"
        print(f"Subject ID derived from '{csv_sub_file}'.")
    else:
        print(f"Subject ID not present in '{csv_sub_file}'. Adding and indexing the subject.")
        if sub_id_df.empty:
            current_bids_subjID = '001'
        else:
            # current_bids_subjID = int(sub_id_df['bids_subjID'].iat[-1]) + 1
            current_bids_subjID = int(np.max(sub_id_df['bids_subjID'].astype(int))) + 1

        new_row = pd.DataFrame({'subjID': [scan.subject], 'bids_subjID': [f"{int(current_bids_subjID):03}"]})
        # display(new_row)
        sub_id_df = pd.concat([sub_id_df, new_row], ignore_index=True)
        
        scan.subject = f"{int(new_row['bids_subjID'].iloc[0]):03}"
    
    print(f"Current subject: {current_subjectID} -> {scan.subject}")

    # display(sub_id_df)
    sub_id_df.to_csv(csv_sub_file, index=False)


    #### populating the participant.tsv file passed in the --part-template flag
    scan.sub_values["original_id"] = current_subjectID


    ### initialize the dataframe for the  sub-<label>_sessions.tsv 
    ### file for this subject
    # Load the JSON file to get the column names
    with open(sessions_tsv_template, 'r') as f:
        sessions_json = json.load(f)
    
    # Extract the column names from the JSON keys
    columns_ses_json = list(sessions_json.keys())

    global subN_sessions_dict
    for col in columns_ses_json:
        subN_sessions_dict[col] = []
    # print(subN_sessions_dict.keys())


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
        ses_id_df = pd.DataFrame(sesIDs_dict, dtype=str)
    else:
        ses_id_df = pd.read_csv(csv_ses_file, dtype={'sesID': str, 'bids_sesID': str})

    global current_sessionID
    current_sessionID = scan.session

    if scan.session in ses_id_df['sesID'].values:
        scan.session = f"{int(ses_id_df.loc[ses_id_df['sesID'] == scan.session, 'bids_sesID'].iloc[0]):02}"
        print(f"Session ID derived from '{csv_ses_file}'.")
    else: 
        print(f"Session ID not present in '{csv_ses_file}'. Adding and indexing the subject.")
        if ses_id_df.empty:
            current_bids_sesID = '01'
        else:
            # current_bids_sesID = int(ses_id_df['bids_sesID'].iat[-1]) + 1
            current_bids_sesID = int(np.max(ses_id_df['bids_sesID'].astype(int))) + 1

        new_row = pd.DataFrame({'sesID': [scan.session], 'bids_sesID': [f"{int(current_bids_sesID):02}"]})
        # display(new_row)
        ses_id_df = pd.concat([ses_id_df, new_row], ignore_index=True)

        scan.session = f"{int(new_row['bids_sesID'].iloc[0]):02}"

    print(f"Current session: {current_sessionID} -> {scan.session}")

    # display(ses_id_df)

    ses_id_df.to_csv(csv_ses_file, index=False)


    ### populating the sub-<label>_sessions.tsv file
    global subN_sessions_dict
    column_ses_dict = list(subN_sessions_dict.keys())

    ## pre-filling all columns with 'n/a' to avoid missing values
    for col in column_ses_dict:
        subN_sessions_dict[col].append('n/a')

    if 'session_id' in column_ses_dict:
        subN_sessions_dict['session_id'][-1] = f"ses-{scan.session}"

    if 'original_session_id' in column_ses_dict:
        if current_sessionID:
            subN_sessions_dict['original_session_id'][-1] = current_sessionID
    # more population of the dictionary in SequenceEP to access a recording object


    # Check if there are sub-directories in the session directory 
    # TODO: this is just a preliminary check to let the user know about this bug. Once the bug is fixed, this should not cause any problems and this check can be removed.
    # scan.in_path yields the path to the session directory
    
    nii_session_dir = f"{scan.in_path}/nii"
    if not Path(nii_session_dir).is_dir():
        logger.warning(f"Directory '{nii_session_dir}' not found. No information about the folder structure in the NIfTI source directory as the sub-directory is not called 'nii/'. Shim current consistency check may not be reliable.")
    else:
        subdirs = [d.name for d in Path(nii_session_dir).iterdir() if d.is_dir()]
        if not subdirs:
            logger.warning(f"No sub-directories found in session directory '{nii_session_dir}'. Shim current consistency check may not be reliable.")
    

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

    def extract_datetime(string):
        # Pattern 1: sYYYY-MM-DD_HH-MM
        pattern1 = r's(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})'
        match = re.match(pattern1, string)
        if match:
            return match.group(1)
        
        # Pattern 2: sYYYYMMDDHHMM
        pattern2 = r's(\d{12})'
        match = re.match(pattern2, string)
        if match:
            datetime_str = match.group(1)
            dt = datetime.strptime(datetime_str, '%Y%m%d%H%M')
            return dt.strftime('%Y-%m-%d_%H-%M')
        
        return None  # No match found


    ### flag to ensure that there are files in the session directory
    global data_avail_in_dir
    data_avail_in_dir = True

    ### count how many shim current relevant sequences are in the session
    rec_id = recording.recId()
    if recording.Module() == "MRI":
        if rec_id.startswith(tuple(shim_current_relevant_recIDs)):  # startswith() checks against each element of the tuple
            global session_shim_current_relevant_sequences_counter
            session_shim_current_relevant_sequences_counter += 1

    ### populating the sub-<label>_sessions.tsv file
    ### performing this in SequenceEP to access the recording object
    ### only add the parameters once per session (ses_dict_populated_for_this_ses)
    global ses_dict_populated_for_this_ses
    if not ses_dict_populated_for_this_ses:
        global subN_sessions_dict
        column_ses_dict = list(subN_sessions_dict.keys())

        if 'acq_time' in column_ses_dict:
            acq_time = extract_datetime(recording.currentFile(True)) # acq_time is ususally stored in the filename
            if acq_time:
                subN_sessions_dict['acq_time'][-1] = acq_time

        if 'scanning_institution' in column_ses_dict:
            scan_institution = recording.getAttribute("InstitutionName")
            if scan_institution:
                subN_sessions_dict['scanning_institution'][-1] = scan_institution
            else: 
                scan_department = recording.getAttribute("InstitutionalDepartmentName")
                if scan_department == "Department":
                    subN_sessions_dict['scanning_institution'][-1] = "(Pecs)"

        if 'manufacturer' in column_ses_dict:
            manufacturer = recording.getAttribute("Manufacturer")
            if manufacturer:
                subN_sessions_dict['manufacturer'][-1] = manufacturer

        if 'scanner_model' in column_ses_dict:
            model = recording.getAttribute("ManufacturersModelName") # dcm2niix
            if not model:
                model = recording.getAttribute("ManufacturerModelName") # SMP / hMRI toolbox DICOM import

            if model:
                subN_sessions_dict['scanner_model'][-1] = model

        if 'field_strength' in column_ses_dict:
            field_strength = recording.getAttribute("MagneticFieldStrength")
            if field_strength:
                subN_sessions_dict['field_strength'][-1] = field_strength

        ## restrict following sequences from populating the sessions.tsv file
        ## this is reset in SessionEndEP
        ses_dict_populated_for_this_ses = True


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

    rec_id = recording.recId()
    if recording.Module() == "MRI":

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
                                  The data may be unusable.""")
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

    # other option to copy bvec and bval files is to define it in FileEP and use 
    # the recording and path objects to determine the according directories 

    if dry_run:
        # Skip if in dry run mode
        return

    # # Run the find command to search for bvec and bval files in the source directory of the current subject and session
    # # only works if there is a single bval and bvec file in the directory
    # bval_file_source = os.popen(f"find {scan.in_path} -name '*.bval'").read().strip()
    # bvec_file_source = os.popen(f"find {scan.in_path} -name '*.bvec'").read().strip()
    
    # if bval_file_source and bvec_file_source:

    #     # Extract the filenames without their extensions
    #     bval_filename, _ = os.path.splitext(os.path.basename(bval_file_source))
    #     bvec_filename, _ = os.path.splitext(os.path.basename(bvec_file_source))
        
    #     if bval_filename == bvec_filename:
    #         bval_path_source = os.path.dirname(bval_file_source)
    #         print(f"Found matching bval and bvec files in {bval_path_source}")

    #         # Extract the file's parent folder from the full path
    #         bval_folder_source = os.path.basename(bval_path_source)

    #         # Use regular expression to find the 4-digit number at the end of the folder name
    #         match = re.search(r'(\d{4})$', bval_folder_source)
    #         if match:
    #             sequence_number_4digit = match.group(1) # 4-digit number (as in source data)
    #             sequence_number_3digit = sequence_number_4digit[1:] # 3-digit number (as in prepared data)

    #         # Run the find command to search for the according files in the prepared data
    #         files_avail_prepared = os.popen(f"find {prep_dir}/{scan.subject}/{scan.session} -name '*{bval_filename}*'").read().strip()
            
    #         # The output will have multiple lines. 
    #         # Split the output into lines and search for the first line that contains the three-digit number
    #         output_paths = files_avail_prepared.split('\n')
    #         correct_path = None
    #         for p in output_paths:
    #             if p:  # Check if path is not empty
    #                 # Get just the filename and its parent directory
    #                 path_parts = p.split(os.sep)
    #                 if len(path_parts) >= 2:
    #                     dir_and_file = os.path.join(path_parts[-2], path_parts[-1])
    #                     if sequence_number_3digit in path_parts[-2]:  # sequence number must be present in the sequence name
    #                         correct_path = p
    #                         break

    #         if correct_path:
    #             bval_path_prepared = os.path.dirname(correct_path)

    #             print(f"Copying bval and bvec files to {bval_path_prepared}")
    #             shutil.copy(bval_file_source, bval_path_prepared)
    #             shutil.copy(bvec_file_source, bval_path_prepared)
    #         else:
    #             logger.warning(f"No matching line found containing the sequence number {sequence_number_3digit}. Please copy the bvec and bval files manually.")

    #     else:
    #         logger.warning("The bval and bvec files do not have the same name. Please check manually.")

    # else:
    #     print(f"No bval or bvec files found in the directories of subject '{current_subjectID}' session '{current_sessionID}'.")
    

    ### populating the sub-<label>_sessions.tsv file with shim current information
    global data_avail_in_dir
    
    if data_avail_in_dir:
        global session_shim_current_warning_counter
        global session_shim_current_relevant_sequences_counter
        global subN_sessions_dict
        column_ses_dict = list(subN_sessions_dict.keys())
        
        if session_shim_current_relevant_sequences_counter in (0, 1): 
            if 'shim_curr_cons' in column_ses_dict:
                logger.warning(f"No information about shim current consistency available in {scan.session} of {scan.subject}.")
                subN_sessions_dict['shim_curr_cons'][-1] = 'n/a' # 0 or 1 relevant sequences do not provide any information about consistent shim currents
        else:
            if session_shim_current_warning_counter == 0:
                logger.info("No shim current inconsistencies present in this session!")
                if 'shim_curr_cons' in column_ses_dict:
                    subN_sessions_dict['shim_curr_cons'][-1] = 'consistent'
            else:
                logger.warning(f"Shim currents are INCONSISTENT in this {scan.session} of {scan.subject}! The data may be unusable.")
                if 'shim_curr_cons' in column_ses_dict:
                    subN_sessions_dict['shim_curr_cons'][-1] = 'inconsistent'

    else:
        print(f"No NIfTI data found in the directories of subject '{current_subjectID}' session '{current_sessionID}'.")


    ## reset shim currents for next session
    global session_shim_currents
    session_shim_currents = None

    ## reset the warning counter for shim currents
    session_shim_current_warning_counter = 0

    ## reset the counter for relevant sequences
    session_shim_current_relevant_sequences_counter = 0

    ## allow the next session to populate the dictionary
    global ses_dict_populated_for_this_ses
    ses_dict_populated_for_this_ses = False

    ## reset data availability flag
    data_avail_in_dir = False


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

    ### saving dictionary to sub-<label>_sessions.tsv file 
    ### for this subject
    global subN_sessions_dict

    print(f"""{scan.subject}_sessions.tsv:
          {subN_sessions_dict}
          ------------------------------------
          """)
          
    df_sessions = pd.DataFrame(subN_sessions_dict)
    if (Path(prep_dir) / scan.subject).is_dir():
        # save sessions.tsv
        output_filename_tsv = f"{prep_dir}/{scan.subject}/{scan.subject}_sessions.tsv"
        df_sessions.to_csv(output_filename_tsv, sep='\t', index=False)
        
        # copy sessions.json
        output_filename_json = f"{prep_dir}/{scan.subject}/{scan.subject}_sessions.json"
        shutil.copy(sessions_tsv_template, output_filename_json)

    # reset the dictionary for the next subject
    subN_sessions_dict = {}


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
