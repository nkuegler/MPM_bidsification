# ATTENTION: This file is used within Python AND Bash. Thus, no spaces around = allowed!


############### Conversion from Dicoms to Nifti using hMRI Dicom Import and dcm2niix ###############
run_dicom_conv=1
path_to_dcm=['/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20240222/dcm',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20240403/dcm',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231121/dcm',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231123/dcm',\
]
path_to_nii=['/data/pt_02262/bids_test/bids_folders_autom/source/37446.6e/20240222/nii2',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/40851.ff/20240403/nii2',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231121/nii2',\
              '/data/pt_02262/bids_test/bids_folders_autom/source/41006.a1/20231123/nii2',\
]

# defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl='noddi'


############### Bidsification of the data set ###############
run_bidsification_from_nii=1
path_to_nii_bids=[]