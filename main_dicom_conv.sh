#!/bin/sh
#!/bin/bash

# $1: input dir
# $2: output dir


mkdir tmp


### defining data to be converted using dcm2niix instead of hMRI Dicom Convert (recommendation: diffusion data)
hMRI_dcmConv_excl="noddi"

### converting DICOMs to Niftis using hMRI toolbox (excluding data in folders containing the exclusion string)

matlab -nodesktop -nosplash -r "call_dicom_conversion('$1','$2','$hMRI_dcmConv_excl')"
echo ">>> hMRI DICOM Import done!"

### converting "excluded" data using dcm2niix
echo ">>> starting dcm2niix conversion"
find $1 -type d -name "*$hMRI_dcmConv_excl*" > tmp/excl_dirs.txt


if [ ! -s tmp/excl_dirs.txt ]; then
    echo "No directories found that contain the pattern '$hMRI_dcmConv_excl'"
else
    while IFS= read -r directory; do
        dcm2niix -o $2 -ba y -b y -f %p_%4s/s%t-%e -z n $directory; 
    done < tmp/excl_dirs.txt
    echo ">>> dcm2niix conversion done"
fi

rm -rf tmp