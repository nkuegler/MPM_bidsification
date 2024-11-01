#!/bin/sh
#!/bin/bash


source settings.py

if [$run_dicom_conv = '1']; then
    echo ">>>> using the variables defined in settings.py"

    if [ ${#path_to_dcm[@]} -ne ${#path_to_nii[@]} ]; then
        echo "Error: The lists path_to_dcm and path_to_nii must have the same length." >&2
        exit 1
    fi

    for i in "${!path_to_dcm[@]}"; do

        if [ ! -d tmp]; then
            mkdir tmp
        fi

        # Create output directory if not present
        if [ ! -d $path_to_nii[$i]]; then
            mkdir $path_to_nii[$i]
        fi

        ### converting DICOMs to Niftis using hMRI toolbox (excluding data in folders containing the exclusion string)
        matlab -nodesktop -nosplash -r "call_dicom_conversion('$path_to_dcm[$i]','$path_to_nii[$i]','$hMRI_dcmConv_excl')"
        echo ">>> hMRI DICOM Import done!"

        ### converting "excluded" data using dcm2niix
        echo ">>> starting dcm2niix conversion"
        find $path_to_dcm[$i] -type d -name "*$hMRI_dcmConv_excl*" > tmp/excl_dirs.txt


        if [ ! -s tmp/excl_dirs.txt ]; then
            echo ">>>> No directories found that contain the pattern '$hMRI_dcmConv_excl'. dcm2niix conversion skipped."
        else
            while IFS= read -r directory; do
                dcm2niix -o $path_to_nii[$i] -ba y -b y -f %p_%4s/s%t-%e -z n $directory; 
            done < tmp/excl_dirs.txt
            echo ">>> dcm2niix conversion done"
        fi

        rm -rf tmp
    
    done


else
    echo ">>>> dicom conversion skipped"
fi





