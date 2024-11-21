#!/bin/bash

# change directory to directory of this script to allow it being called from anywhere
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

source settings.py


function adjust_path {
    # Function: adjust_path
    # Description: Adjusts the given path string by ensuring it ends with a '/'.
    # Arguments:
    #   $1 - A string representing the path to be adjusted.
    # Returns:
    #   The adjusted path string with a trailing '/' if it was not already present.

    path_string=$1
    if [[ "${path_string: -1}" != "/" ]]; then
        path_string="${path_string}/"
    fi
    echo $path_string
}


# variable name where the last path for dcm and nii are stored
last_dcm_path_name="path_to_dcm${number_of_paths}"
last_nii_path_name="path_to_nii${number_of_paths}"

tmp_dir="tmp"

if [[ $run_dicom_conv = "1" ]]; then
    echo ">>>> Running Dicom to Nifti Conversion"
    echo ">>>> using the variables defined in settings.py"

    if [[ -z ${!last_dcm_path_name} ]] || [[ -z ${!last_nii_path_name} ]]; then         ## TODO: loop over all integers until number_of_paths and check if dcm and nii are specified.
        echo "Error: There must be as many path_to_dcm as path_to_nii specified in the settings file." #>&2     ## best to include in loop further down
        exit 1
    else
        echo ">>>> Number of directories to convert: ${number_of_paths}"
    fi

    if [[ ! -d $tmp_dir ]]; then
        mkdir $tmp_dir
    fi

    for i in $(seq 1 $number_of_paths); do
        echo "---------------------------------------"
        
        curr_path_to_dcm="path_to_dcm${i}"
        curr_path_to_nii="path_to_nii${i}"

        # if paths are not defined with '/' at the end, the find command will not work recursively
        curr_path_to_dcm=$(adjust_path ${!curr_path_to_dcm})
        curr_path_to_nii=$(adjust_path ${!curr_path_to_nii})

        # Create output directory if not present
        if [[ ! -d $curr_path_to_nii ]]; then
            mkdir $curr_path_to_nii
        fi

        ### converting DICOMs to Niftis using hMRI toolbox (excluding data in folders containing the exclusion string)
        MATLAB matlab -nodesktop -nosplash -r "call_dicom_conversion('$curr_path_to_dcm','$curr_path_to_nii','$hMRI_dcmConv_excl', false)";exit
        echo ">>> hMRI DICOM Import done!"

        ### converting "excluded" data using dcm2niix
        echo ">>> starting dcm2niix conversion"
        dirs_txt_fname=excl_dirs_$(date +"%Y%m%d_%H%M%S").txt
        find $curr_path_to_dcm -type d -iname "*$hMRI_dcmConv_excl*" > $tmp_dir/$dirs_txt_fname


        if [[ ! -s $tmp_dir/$dirs_txt_fname ]]; then
            echo ">>>> No directories found that contain the pattern '$hMRI_dcmConv_excl'. dcm2niix conversion skipped."
        else
            while IFS= read -r directory; do
                dcm2niix -o $curr_path_to_nii -ba y -b y -f %p_%4s/s%t-%e -z n $directory; 
            done < $tmp_dir/$dirs_txt_fname
            echo ">>> dcm2niix conversion done"
        fi

        rm -f $tmp_dir/$dirs_txt_fname
    
    done

    rm -rf $tmp_dir


else
    echo ">>>> dicom conversion skipped"
fi