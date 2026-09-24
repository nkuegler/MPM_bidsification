#!/bin/bash

# $1: input_dir
# $2: output_dir

# change directory to directory of this script to allow it being called from anywhere
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR


function adjust_path {
    # pass a string (path) as argument
    # check if the last character in the string is a '/'
    # if not, add a '/' to the end
    # return the updated string
    path_string=$1
    if [[ "${path_string: -1}" != "/" ]]; then
        path_string="${path_string}/"
    fi
    echo $path_string
}


# if paths are not defined with '/' at the end, the find command will not work recursively
input_dir=$(adjust_path $1)
output_dir=$(adjust_path $2)

tmp_dir="tmp2"

if [[ ! -d $tmp_dir ]]; then
    mkdir $tmp_dir
fi

SPM_DICOM_BASENAME="DICOM-to-NIfTI" # if parent directory of call_dicom_conversion.m ever changes
parent_dir="$(dirname "${SCRIPT_DIR}")"
SPM_DICOM_DIR="$parent_dir/$SPM_DICOM_BASENAME"
# check if SPM_DICOM_DIR is in DICOM-to-NIfTI
if [[ ! -d "$SPM_DICOM_DIR" ]]; then
    echo "Error: directory '$SPM_DICOM_BASENAME' does not exist, or is not within $parent_dir/"
    exit 1
else
    echo "directory found $SPM_DICOM_DIR"
fi

### defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl="noddi"

### converting DICOMs to Niftis using hMRI toolbox (excluding data in folders containing the exclusion string)

matlab -nodesktop -nosplash -sd"$SPM_DICOM_DIR" -r "call_dicom_conversion('$input_dir','$output_dir','$hMRI_dcmConv_excl')"
echo ">>> hMRI DICOM Import done!"

### converting "excluded" data using dcm2niix
echo ">>> starting dcm2niix conversion"
dirs_txt_fname=excl_dirs_$(date +"%Y%m%d_%H%M%S").txt
find $input_dir \( -type d -o -xtype d \) -name "*$hMRI_dcmConv_excl*" > $tmp_dir/$dirs_txt_fname


if [[ ! -s $tmp_dir/$dirs_txt_fname ]]; then
    echo "No directories found that contain the pattern '$hMRI_dcmConv_excl'"
else
    while IFS= read -r directory; do
        dcm2niix -o $output_dir -ba y -b y -f %p_%4s/s%t-%e -z n $directory; 
    done < $tmp_dir/$dirs_txt_fname
    echo ">>> dcm2niix conversion done"
fi

rm -rf $tmp_dir