% author: Ilona Lipp 
% repository: https://github.com/IlonaLipp/postmortembrain-mpm
% adjusted by: Niklas Kuegler


function convert_dicoms_to_nifti_no_check(dicom_data_dir, nifti_data_dir, avoid_folders, avoid_criterium)
    %% runs loop over all raw data dicom folders to convert to nifti
    %% uses hMRI toolbox batch, so needs to be run from SPM environment
    %%% this function does not check if the conversion has been done correctly
    %%% in different ways (this check does not work for certain sequences (in
    %%% particular DTI). if you want to check, use the function
    %%% "convert_dicoms_to_nifti.m"
    
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


    %%% hMRI toolbox for dicom conversion
    %%% raw data are .ima images; convert dicoms in all folders to nifti files 
    for folder = 1:length(foldernames)
        
        %%% check whether has already been done
        str_to_check = foldernames(folder).name;

        if str_to_check(1) == '_'  % avoid errors due to empty array elements after splitting at '_'
            str_to_check = str_to_check(2:end); 
        end

        str_to_check_2 = strsplit(str_to_check, '_');

        %% Leipzig data directory naming convention: 'S<sequence_number>_<sequence_name>'
        if strcmp(str_to_check_2{1}(1),'S')
            str_to_check_3 = strsplit(str_to_check_2{1}, 'S');
            sequence_number = str2num(str_to_check_3{2});
        else
            sequence_number = str2num(str_to_check_2{1});
        end

        %% Liege data directory naming convention: '<sequence_name>_<sequence_number>'
        if isempty(sequence_number)
            sequence_number = str2num(str_to_check_2{end});
        end

        nifti_files_there = dir([nifti_data_dir,'/*',sprintf('%04d',sequence_number),'/*.nii']);

        if length(nifti_files_there) == 0 && sequence_number ~= 99 && ~contains(str_to_check,'[')  %%% only do conversion if no nifti files are in the folder and if is not the stupid phoenix report sequence

            %%% check for files with .ima extension, as for Leipzig scanner
            filenames = dir([foldernames(folder).folder,'/',foldernames(folder).name,'/*.ima']);
            %%% if no files are found, check for filenames with MR at
            %%% beginning, as for Magdeburg scanner
            if length(filenames) == 0
                filenames = dir([foldernames(folder).folder,'/',foldernames(folder).name,'/MR*']);
            end
            %%% check for files with .dcm extension (DICOM data), e.g. Leipzig scanner
            if length(filenames) == 0
                filenames = dir([foldernames(folder).folder,'/',foldernames(folder).name,'/*.dcm']);
            end
            %%% check for files with .IMA extension, as for Liege scanner
            if length(filenames) == 0
                filenames = dir([foldernames(folder).folder,'/',foldernames(folder).name,'/*.IMA']);
            end

            if length(filenames) > 0
                %%% save name of all dicoms in a cell array
                for file = 1:length(filenames)
                    filename_structure{file} = [foldernames(folder).folder,'/',foldernames(folder).name,'/',filenames(file).name];
                end
                %%% define an spm job
                spm_jobman('initcfg');
                spm('defaults', 'FMRI');
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.data = filename_structure'; %%% as a batch can include several steps, we put the conversion as first step {1},  put as input all files in dir
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.outdir = {nifti_data_dir}; %%% set output directory
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.protfilter = '.*';
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.format = 'nii';
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.root = 'series';
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.metaopts.mformat = 'sep'; %%% luke's script needs json files
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.convopts.icedims = 0; %%% try setting to 0
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.data;
                dicom2nifti_batch{1}.spm.tools.hmri.dicom.outdir
                display('converting sequence')
                nifti_data_dir
                sequence_number
                
                spm_jobman('run',dicom2nifti_batch);
                
            end
        end
    end
end