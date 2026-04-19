# ATTENTION: This file is used within Python AND Bash. Thus, no spaces around = allowed!


############### Conversion from Dicoms to Nifti using hMRI Dicom Import and dcm2niix ###############

# defining the path to the dicom data and the path to the nifti data
# bash cannot handle lists of strings, thus we need to define each path separately
# number_of_paths specifies the last directory to be processed (e.g. 4 means 4 path_to_dcm4 and path_to_nii4)
number_of_paths=5

# start the index at 1
#### subject 37446.6e
# path_to_dcm1="/data/pt_02262/data/TH_bids/source/37446.6e/20230703_1/dcm"
# path_to_nii1="/data/pt_02262/data/TH_bids/source/37446.6e/20230703_1/nii"

# path_to_dcm2="/data/pt_02262/data/TH_bids/source/37446.6e/20230703_2/dcm"
# path_to_nii2="/data/pt_02262/data/TH_bids/source/37446.6e/20230703_2/nii"

# path_to_dcm1="/data/pt_02262/data/TH_bids/source/37446.6e/20231222/dcm"
# path_to_nii1="/data/pt_02262/data/TH_bids/source/37446.6e/20231222/nii"

# path_to_dcm1="/data/pt_02262/data/TH_bids/source/37446.6e/20230505/dcm"
# path_to_nii1="/data/pt_02262/data/TH_bids/source/37446.6e/20230505/nii"

# path_to_dcm2="/data/pt_02262/data/TH_bids/source/37446.6e/20230511/dcm" ## not working atm (?)
# path_to_nii2="/data/pt_02262/data/TH_bids/source/37446.6e/20230511/nii"

# path_to_dcm3="/data/pt_02262/data/TH_bids/source/37446.6e/20230512/dcm"
# path_to_nii3="/data/pt_02262/data/TH_bids/source/37446.6e/20230512/nii"

# path_to_dcm4="/data/pt_02262/data/TH_bids/source/37446.6e/20240222/dcm"
# path_to_nii4="/data/pt_02262/data/TH_bids/source/37446.6e/20240222/nii"

#### subject 40851.ff
# path_to_dcm4="/data/pt_02262/data/TH_bids/source/40851.ff/20230703/dcm"
# path_to_nii4="/data/pt_02262/data/TH_bids/source/40851.ff/20230703/nii"

# path_to_dcm5="/data/pt_02262/data/TH_bids/source/40851.ff/20230704/dcm"
# path_to_nii5="/data/pt_02262/data/TH_bids/source/40851.ff/20230704/nii"

#path_to_dcm1="/data/pt_02262/data/TH_bids/source/40851.ff/20231221/dcm"
#path_to_nii1="/data/pt_02262/data/TH_bids/source/40851.ff/20231221/nii"

#path_to_dcm2="/data/pt_02262/data/TH_bids/source/40851.ff/20231222/dcm"
#path_to_nii2="/data/pt_02262/data/TH_bids/source/40851.ff/20231222/nii"

# path_to_dcm5="/data/pt_02262/data/TH_bids/source/40851.ff/20230505/dcm"
# path_to_nii5="/data/pt_02262/data/TH_bids/source/40851.ff/20230505/nii"

# path_to_dcm6="/data/pt_02262/data/TH_bids/source/40851.ff/20230511/dcm"
# path_to_nii6="/data/pt_02262/data/TH_bids/source/40851.ff/20230511/nii"

# path_to_dcm7="/data/pt_02262/data/TH_bids/source/40851.ff/20230512/dcm"
# path_to_nii7="/data/pt_02262/data/TH_bids/source/40851.ff/20230512/nii"

# path_to_dcm8="/data/pt_02262/data/TH_bids/source/40851.ff/20240403/dcm"
# path_to_nii8="/data/pt_02262/data/TH_bids/source/40851.ff/20240403/nii"

#### subject 41006.a1
# path_to_dcm9="/data/pt_02262/data/TH_bids/source/41006.a1/20230606/dcm"
# path_to_nii9="/data/pt_02262/data/TH_bids/source/41006.a1/20230606/nii"

# path_to_dcm1="/data/pt_02262/data/TH_bids/source/41006.a1/20231012/dcm"
# path_to_nii1="/data/pt_02262/data/TH_bids/source/41006.a1/20231012/nii"

# path_to_dcm10="/data/pt_02262/data/TH_bids/source/41006.a1/20231121/dcm"
# path_to_nii10="/data/pt_02262/data/TH_bids/source/41006.a1/20231121/nii"

# path_to_dcm11="/data/pt_02262/data/TH_bids/source/41006.a1/20231123/dcm"
# path_to_nii11="/data/pt_02262/data/TH_bids/source/41006.a1/20231123/nii"

#### subject 41486.2c
# path_to_dcm12="/data/pt_02262/data/TH_bids/source/41486.2c/20230928/dcm"
# path_to_nii12="/data/pt_02262/data/TH_bids/source/41486.2c/20230928/nii"

# path_to_dcm1="/data/pt_02262/data/TH_bids/source/41486.2c/20231006/dcm"
# path_to_nii1="/data/pt_02262/data/TH_bids/source/41486.2c/20231006/nii"

# path_to_dcm2="/data/pt_02262/data/TH_bids/source/41486.2c/20231010/dcm"
# path_to_nii2="/data/pt_02262/data/TH_bids/source/41486.2c/20231010/nii"

#### subject 5perlaki

path_to_dcm1="/data/pt_02262/data/TH_bids/source/5perlaki/20231012/dcm"
path_to_nii1="/data/pt_02262/data/TH_bids/source/5perlaki/20231012/nii"

path_to_dcm2="/data/pt_02262/data/TH_bids/source/5perlaki/20241126_1/dcm"
path_to_nii2="/data/pt_02262/data/TH_bids/source/5perlaki/20241126_1/nii"

path_to_dcm3="/data/pt_02262/data/TH_bids/source/5perlaki/20241126_2/dcm"
path_to_nii3="/data/pt_02262/data/TH_bids/source/5perlaki/20241126_2/nii"

path_to_dcm4="/data/pt_02262/data/TH_bids/source/5perlaki/20230303/dcm"
path_to_nii4="/data/pt_02262/data/TH_bids/source/5perlaki/20230303/nii"

path_to_dcm5="/data/pt_02262/data/TH_bids/source/5perlaki/20230508/dcm"
path_to_nii5="/data/pt_02262/data/TH_bids/source/5perlaki/20230508/nii"

# defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl='noddi' # case invariant comparison


############### Bidsification of the data set ###############
run_bidsification_from_nii=0
path_to_nii_bids=[]