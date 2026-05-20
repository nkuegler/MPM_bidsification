% author: Niklas Kuegler
% repository: https://github.com/IronSleep/MPM_bidsification
% License: MIT Copyright (c) 2026 Niklas Kuegler (nkuegler)


function convert_dicoms_to_nifti_simple(dicom_data_dir, nifti_data_dir, avoid_folders, avoid_criterium)
    %% % Scan all matching DICOM subfolders, collect every file ending in .dcm, .ima, or .IMA into one combined list, and run a single SPM/hMRI toolbox DICOM-to-NIfTI conversion batch for all of them at once.
    %% Safety checks before conversion: optionally exclude folders by name pattern, abort immediately if the output directory is not empty (or if no matching DICOM files are found).
    %% needs to be run from SPM environment (hMRI toolbox batch)
    
    foldernames = dir([dicom_data_dir,'/*_*']); %%% just consider folders that have underscores in them
    

    if avoid_folders
        if ischar(avoid_criterium)
            rows_to_delete = [];
            for i = 1:length(foldernames)
                if contains(foldernames(i).name, avoid_criterium, 'IgnoreCase', true)
                    rows_to_delete = [rows_to_delete, i];
                end
            end
            disp("Avoiding all folders that contain the string '" + avoid_criterium + "'.")
            foldernames(rows_to_delete) = [];
        else
            disp("avoid_criterium has to be specified as character array.")
        end
    else
        disp("Including all folders in the input directory!")
    end

    %% fail fast if output directory is not empty
    output_dir_contents = dir(nifti_data_dir);
    output_dir_contents = output_dir_contents(~ismember({output_dir_contents.name}, {'.', '..'}));
    if ~isempty(output_dir_contents)
        error('Output directory is not empty: %s', nifti_data_dir);
    end


    %%% hMRI toolbox for dicom conversion
    %%% collect all dicoms (.dcm/.ima/.IMA) from all folders and convert in one batch
    filename_structure = {};

    for folder = 1:length(foldernames)
        folder_path = [foldernames(folder).folder,'/',foldernames(folder).name];
        files_dcm = dir([folder_path,'/*.dcm']);
        files_ima = dir([folder_path,'/*.ima']);
        files_IMA = dir([folder_path,'/*.IMA']);
        files_in_folder = [files_dcm; files_ima; files_IMA];

        for file = 1:length(files_in_folder)
            filename_structure{end+1,1} = [folder_path,'/',files_in_folder(file).name];
        end
    end

    if isempty(filename_structure)
        fprintf('No DICOM files with .dcm, .ima, or .IMA suffix found in: %s\n', dicom_data_dir);
        return;
    end

    %%% define and run one spm job for all discovered files
    clear dicom2nifti_batch
    spm_jobman('initcfg');
    spm('defaults', 'FMRI');
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.data = filename_structure;
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.outdir = {nifti_data_dir}; %%% set output directory
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.protfilter = '.*';
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.format = 'nii';
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.root = 'series';
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.metaopts.mformat = 'sep'; %%% luke's script needs json files
    dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.icedims = 0; %%% try setting to 0

    disp(['Converting ', num2str(length(filename_structure)), ' DICOM files...'])
    spm_jobman('run',dicom2nifti_batch);
end