function dcm2nii_matlab_version(folders)
%folders = struct2table(dir('/data/u_krohn_software/links_to_relevant_dirs/histopark/in_vivo/source/40135.5a/20260421/dcm/*'));
if ischar(folders)
    folders = struct2table(dir([folders,'/*']));
end
for a = 1:height(folders)
    curr_folder = fullfile(folders.folder{a}, folders.name{a});
    outdirname = folders.name{a};
    session_dir = fileparts(fileparts(curr_folder));
    outdir = fullfile(session_dir, 'dcm2niix', outdirname);
    if exist(outdir, 'dir') == 0
        mkdir(outdir)
    end
    cmd = ['dcm2niix -o "', outdir, '" -ba y -b y -f %p_%4s/s%t-%e -z n "', curr_folder, '"'];
    if isempty(mydir(outdir))
    disp(cmd)
    system(cmd)
    end
end