# ATTENTION: This file is used within Python AND Bash. Thus, no spaces around = allowed!


############### Conversion from Dicoms to Nifti using hMRI Dicom Import and dcm2niix ###############
run_dicom_conv=1

# defining the path to the dicom data and the path to the nifti data
# bash cannot handle lists of strings, thus we need to define each path separately
# number_of_paths specifies the last directory to be processed (e.g. 4 means 4 path_to_dcm4 and path_to_nii4)
number_of_paths=7

# start the index at 1
# subject 1
path_to_dcm1="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230505/dcm"
path_to_nii1="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230505/nii"

# path_to_dcm2="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230511/dcm"
# path_to_nii2="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230511/nii"

# path_to_dcm3="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230512/dcm"
# path_to_nii3="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20230512/nii"

path_to_dcm2="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20240222/dcm"
path_to_nii2="/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20240222/nii"

# subject 2
# path_to_dcm5="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20230511/dcm"
# path_to_nii5="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20230511/nii"

# path_to_dcm6="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20230512/dcm"
# path_to_nii6="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20230512/nii"

path_to_dcm3="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20240403/dcm"
path_to_nii3="/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20240403/nii"

# subject 3
path_to_dcm4="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20230606/dcm"
path_to_nii4="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20230606/nii"

path_to_dcm5="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231121/dcm"
path_to_nii5="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231121/nii"

path_to_dcm6="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231123/dcm"
path_to_nii6="/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231123/nii"

# subject 4
path_to_dcm7="/data/pt_02262/bids_test/bids_folders_autom/source/41486.2c/20230928/dcm"
path_to_nii7="/data/pt_02262/bids_test/bids_folders_autom/source/41486.2c/20230928/nii"

# defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl='noddi'


############### Bidsification of the data set ###############
run_bidsification_from_nii=0
path_to_nii_bids=[]