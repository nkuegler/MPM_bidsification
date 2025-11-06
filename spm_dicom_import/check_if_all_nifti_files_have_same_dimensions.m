% author: Ilona Lipp 
% repository: https://github.com/IlonaLipp/postmortembrain-mpm
% License: CC0 1.0 Universal (public domain dedication)

function correct_or_not = check_if_all_nifti_files_have_same_dimensions(nifti_files_produced)
    %%% this is just a function to check whether dicom conversion has been
    %%% done properly. it goes through the list of nifti files it gets as
    %%% an argument, checks the dimensions and compares them. it spits out
    %%% a variable correct_or_not, that is set to 1 if all have the same
    %%% dimensions or 0 if not
    correct_or_not = 1; %%% set to correct
    for niftifile = 1:length(nifti_files_produced)
        filename = [nifti_files_produced(niftifile).folder, '/', nifti_files_produced(niftifile).name];
        VCON = spm_vol(filename);
        if niftifile == 1
           first_dim = VCON.dim;
        else
           current_dim = VCON.dim;
           if isequal(first_dim, current_dim) == 0 %%% something is wrong
               correct_or_not = 0;
               break
           end
        end
    end
end