function call_dicom_conversion(input_dir, output_dir, excl_str, spm_path, hmri_toolbox_path, dicom_import_path)
    %% function calling Ilona Lipps function to convert DICOMs to Niftis 
    %% using the hMRI toolbox DICOM import

    % input_dirs is supposed to be a txt-file with all the directories
    % output_dir is supposed to be a string
    
    %% text file idea
    %output_dir = convertCharsToStrings(output_dir);

    % all_input_dirs = fileread(input_dirs);
    % separate_dirs = strsplit(all_input_dirs, '\n');


    % for i = 1:length(separate_dirs)
    %     current_dir_str = convertCharsToStrings(separate_dirs{i});
    %     disp(current_dir_str);
    %    convert_dicoms_to_nifti(current_dir_str,output_dir, 0);
    % end

    addpath(spm_path)
    addpath(hmri_toolbox_path)
    addpath(dicom_import_path)

    disp("Retrieving DICOMs from " + input_dir)


    % Scan all matching DICOM subfolders, collect every file ending in .dcm, .ima, or .IMA into one combined list, and run a single SPM/hMRI toolbox DICOM-to-NIfTI conversion batch for all of them at once.
    % Safety checks before conversion: optionally exclude folders by name pattern, abort immediately if the output directory is not empty (or if no matching DICOM files are found).
    convert_dicoms_to_nifti_simple(input_dir, output_dir, true, excl_str)

    exit

