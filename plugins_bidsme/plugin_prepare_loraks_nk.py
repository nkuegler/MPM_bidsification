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
import plugin_helper_functions as helper

# Will integrate plugin into logging
import logging

logger = logging.getLogger(__name__)

plugin_path = os.path.dirname(__file__)
resources_path = os.path.dirname(plugin_path)

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
corresponding_bids_data_path = ""
available_contrasts_loraks = ["t1w_kp_mtflash3d", "pdw_kp_mtflash3d", "mtw_kp_mtflash3d", "ernst_kp_mtflash3d"] # "kp_afib1" # AFI B1 not possible due to uncertainty about the correct repetition time
smap_ident = "smap_kp_mtflash3d"

def remove_trailing_slash(path):
    ## making sure that there is no trailing slash
    return path[:-1] if path.endswith('/') else path

# list of sequences in order of acquisition in current session
files_list = list()

# The index of current sequence, corresponds to order in the sequence list
file_index = -1


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

    global corresponding_bids_data_path
    corresponding_bids_data_path = os.path.abspath(os.path.join(nifti_dir, '..', 'bids')) # works for: source dir is on the same level as bids dir
    if not os.path.exists(corresponding_bids_data_path):
        raise exceptions.InitEPError(f"Corresponding BIDS directory not found at {corresponding_bids_data_path}")

    global include_smaps
    include_smaps = kwargs.get("include_smaps", False)
    include_smaps = helper.argument_to_bool(include_smaps)
    if include_smaps == -1:
        raise exceptions.InitEPError(f"Invalid value for 'include_smaps' in plugin options")

    print("options passed to plugin:")
    print(f"- include_smaps: {include_smaps}")

    global available_contrasts_loraks
    global smap_ident
    if include_smaps:
        new_list = []
        for item in available_contrasts_loraks:
            new_list.append(smap_ident)
            new_list.append(item)
        available_contrasts_loraks = new_list
    
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

    global file_index
    file_index = -1

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


    global files_list

    # create a list of all files in the directory -> strip that list by all elements that do not contain ".nii" (or ".nii.gz")
    current_dir = os.path.dirname(recording.currentFile(False))
    files_list = [f for f in os.listdir(current_dir) if os.path.isfile(os.path.join(current_dir, f)) and '.nii' in f]
    files_list = sorted(files_list)
    # print(f"NIfTI files in {current_dir}: {files_list}")


    ### flag to ensure that there are files in the session directory
    global data_avail_in_dir
    data_avail_in_dir = True

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

    def get_series_id(str_to_check, recording):
        # case-insensitive check, but preserves the original casing in the returned series_id
        filename = recording.currentFile(True)
        # Find the start position using case-insensitive search
        lower_filename = filename.lower()
        lower_str = str_to_check.lower()
        start_pos = lower_filename.find(lower_str)
        
        if start_pos == -1:
            # Fallback if not found (shouldn't happen in normal flow)
            recording_id_rest = filename.split(str_to_check)[1].split("_rec")[0]
            series_id = f"{str_to_check}{recording_id_rest}"
        else:
            # Extract the original-cased version from the filename
            original_cased_str = filename[start_pos:start_pos + len(str_to_check)]
            # Get the rest of the ID after the matched string
            remaining = filename[start_pos + len(str_to_check):]
            recording_id_rest = remaining.split("_rec")[0]
            series_id = f"{original_cased_str}{recording_id_rest}"
        
        return series_id

    global file_index
    global available_contrasts_loraks

    if recording.Module() == "MRI":
        file_index += 1
        # print(f"{file_index}: {recording.currentFile(True)}")


        ## evaluate whether _loraks or _loraksRsos is present in the filename
        recon_method = ""

        if "rec-loraksRsos".casefold() in recording.currentFile(True).casefold():
            recon_method = "loraksRsos"
            rsos_factor = 1
        elif "rec-loraks".casefold() in recording.currentFile(True).casefold():
            recon_method = "loraks"
            rsos_factor = 0
        else:
            return 0
        
        if recon_method:
            if not include_smaps:
                for ind, contrast_fname in enumerate(available_contrasts_loraks):
                    if contrast_fname.casefold() in recording.currentFile(True).casefold():
                        recording.series_id = f"{get_series_id(contrast_fname, recording)}_{recon_method}"
                        recording.series_no = int(np.arange(1, len(available_contrasts_loraks*2), 2)[ind] + rsos_factor) # first element in list = 1, second = 3, third = 5

            else: 
                if smap_ident.casefold() in recording.currentFile(True).casefold():
                    # determine the contrast which the sensitivity map was acquired for by looking at the following sequences
                    smap_modality = helper.find_smap_modality(files_list, file_index)
                    if smap_modality:
                        recording.series_id = f"{get_series_id(smap_ident, recording)}_{smap_modality}_{recon_method}"
                        # find the index of the according contrast in the available_contrast_array (generator returns only the first element containing the string!)
                        smap_modal_idx = next((i for i, elem in enumerate(available_contrasts_loraks) if smap_modality.casefold() in elem.casefold()), None)
                        # use (smap_modal_idx - 1) as index of the smap
                        recording.series_no = int(np.arange(1, len(available_contrasts_loraks*2), 2)[smap_modal_idx-1] + rsos_factor) # smap always right before corresponding contrast

                    else:
                        logger.warning("{}: Unable to determine modality of sensitivity map"
                                .format(recording.recIdentity()))
                
                else:
                    for ind, contrast_fname in enumerate(available_contrasts_loraks):
                        if contrast_fname.casefold() in recording.currentFile(True).casefold():
                            recording.series_id = f"{get_series_id(contrast_fname, recording)}_{recon_method}"
                            recording.series_no = int(np.arange(1, len(available_contrasts_loraks*2), 2)[ind] + rsos_factor) # first element in list = 1, second = 3, third = 5
                
                # print(f"series_id: {recording.series_id}")
                # print(f"series_no: {recording.series_no}")


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

    ## copy shim current inconsistency information from sessions.tsv in the bidsified data set to the one in the LORAKS directory 
    global subN_sessions_dict

    sessions_tsv_bids = os.path.join(corresponding_bids_data_path, scan.subject, f"{scan.subject}_sessions.tsv")
    if os.path.isfile(sessions_tsv_bids):
        df = pd.read_csv(sessions_tsv_bids, sep='\t')
        target_row = df[df['session_id'] == scan.session]
        shim_curr_cons = target_row['shim_curr_cons'].values[0]
        
        if shim_curr_cons == 'consistent':
            logger.info(f"No shim current inconsistencies present in this session!")
        elif shim_curr_cons == 'inconsistent':
            logger.warning(f"Shim currents are INCONSISTENT in this {scan.session} of {scan.subject}! The data may be unusable.")
        else:
            logger.warning(f"""NO INFORMATION on shim current consistency available for {scan.session} of {scan.subject}.
                           Please check the manually!""")
            shim_curr_cons = 'n/a'

        column_ses_dict = list(subN_sessions_dict.keys())
        if 'shim_curr_cons' in column_ses_dict:
            subN_sessions_dict['shim_curr_cons'][-1] = shim_curr_cons

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
