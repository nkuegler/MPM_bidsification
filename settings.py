# ATTENTION: This file is used within Python AND Bash. Thus, no spaces around = allowed!


############### Conversion from Dicoms to Nifti using hMRI Dicom Import and dcm2niix ###############
run_dicom_conv=1

# defining the path to the dicom data and the path to the nifti data
# bash cannot handle lists of strings, thus we need to define each path separately
# number_of_paths specifies the last directory to be processed (e.g. 4 means 4 path_to_dcm4 and path_to_nii4)
number_of_paths=1

# start the index at 1
# subject 1
path_to_dcm1="/data/pt_02262/bids_test/alinadata/source/NRO-271/20241105/dcm"
path_to_nii1="/data/pt_02262/bids_test/alinadata/source/NRO-271/20241105/nii2"

# defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl='noddi' # case invariant comparison


############### Bidsification of the data set ###############
run_bidsification_from_nii=0
path_to_nii_bids=[]