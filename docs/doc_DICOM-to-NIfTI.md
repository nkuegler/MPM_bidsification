# Documentation of the DICOM-to-NIfTI inversion step

> [!WARNING]  
> The DICOM-import scripts seem to not be working reliably and must be replaced by a more robust solution. 
> For now, the best workaround is to either use the SPM GUI (Batch Editor -> SPM -> Tools -> hMRI Tools -> DICOM Import) or to convert the DICOM data using dcm2niix.

This page describes the conversion of the scanner-reconstructed DICOM data to the NIfTI format. 

The scripts that are described on this page are part of the **MPM_bidsification** repository ([Github](https://github.com/IronSleep/MPM_bidsification), [Gitlab](https://gitlab.gwdg.de/cbs-neurophy/bidsification_mpm)). Feel free to clone or fork the repository. If you encounter any problems, [send me an e-mail](mailto:kuegler@cbs.mpg.de?subject=Problems%20with%20MPM_bidsification) or a message on the Minerva Messenger (user: kuegler). <br>
The repository also contains the scripts for performing the [Bidsification of the data](doc_bidsification.md).


## Table of Contents
1. [Usage](#usage)
    - [Necessary software (repositories)](#necessary-software-repositories)
    - [How to run the DICOM-to-NIfTI conversion](#how-to-run-the-dicom-to-nifti-conversion)
        - [Full dcm2niix conversion (alternative)](#full-dcm2niix-conversion-alternative)
2. [File description](#file-description)
3. [ToDos](#todos)

## Usage

For a smooth function of the hMRI toolbox (in a later processing module of the data analysis pipeline) for creating quantitative parameter maps from the weighted images (acquired using the MPM protocol), it is necessary to export all the relevant metadata. In BIDS-conform data sets, NIfTI files are accompanied by sidecar JSON files, which contain all metadata and parameter information. <br>
To assure that all the necessary metadata is exported correctly from the DICOM header to the sidecar JSON files, the **DICOM Import** of **SPM** is used. <br>
However, this conversion is not optimal for diffusion data, as it doesn't convert the data into a 4-dimensional array (as specified by the BIDS standard) and also lacks the ability to create the required _.bvec_ and _.bval_ files. Therefore, there is an option to skip files whose names contain a certain string during the DICOM Import and automatically convert them using **dcm2niix** (e.g., the parameter `hMRI_dcmConv_excl = "noddi"` can be specified in the settings file).

>**Hint:**<br>
If data is already present in the specified NIfTI directory (output directory), the DICOM-to-NIfTI conversion of the corresponding session is skipped. Old data will **NOT** be overwritten.
Conversion is also skipped for DICOM data of sequences that have the series number 99 or whose name contains the string "\[" (opening square bracket).


### Necessary software (repositories)

+ **MPM_bidsification**
    + The versions on the [Neurophysics Gitlab](https://gitlab.gwdg.de/cbs-neurophy/bidsification_mpm) and the [IronSleep Github](https://github.com/IronSleep/MPM_bidsification) are identical (synced). However, access to both repositories is restricted. Reach out if you want to access the code ([kuegler@cbs.mpg.de](mailto:kuegler@cbs.mpg.de?subject=Permissions%20missing%20MPM_bidsification)).
+ **hMRI toolbox (+ SPM)**
    + The hMRI toolbox is part of SPM. Therefore the SPM repository and the hMRI toolbox repository must be cloned and the dependencies adjusted accordingly. Please follow the instructions on the [*Get Started* page on the hMRI-Toolbox-Wiki](https://github.com/hMRI-group/hMRI-toolbox/wiki/GetStarted) for more information on the installation and on how to include the toolbox in SPM. You don't need to add paths in your MATLAB version, as this is handled by a script (see Step 4 later on this page).
    + The [production version on Github](https://github.com/hMRI-group/hMRI-toolbox) should be used in most cases. For data of the IronSleep project, please use the [forked version on the IronSleep Github](https://github.com/IronSleep/hMRI-toolbox) _(restricted access)_.
+ **dcm2niix**
    + You can either clone the [Github repository](https://github.com/rordenlab/dcm2niix) or download the [MRIcroGL viewer](https://www.nitrc.org/projects/mricrogl/) which includes dcm2niix as graphical interface.
    + Other install options are by using conda/mamba, pip, apt-get, or brew (see the instructions in the Github repository).
    + You can find more information in the [documentation of dcm2niix](https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#General_Usage), which includes details on *bvec* & *bval* file creation in the DTI section.
+ ***(postmortembrain-mpm)***
    + The main DICOM import functions were taken and adjusted from Ilona Lipp's [postmortem-brain Github repository](https://github.com/IlonaLipp/postmortembrain-mpm).
    + You **don't** need to clone this repository as the required MATLAB functions were adjusted and included in the **MPM_Bidsification** repository (in the `spm_dicom_import/` directory).
+ ***(Bidsme for Bidsification)***
    + More on that in the [Bidsification step](doc_bidsification.md). You **don't** need to manually install *Bidsme*. The **MPM_bidsification** repository provides an environment YAML file (`supplementary/bidsme_env.yml`) that you can use to create a proper conda environment including *Bidsme* and all its dependencies. How to create the environment from the YAML file is described in the steps below.



### How to run the DICOM-to-NIfTI conversion

The conversion is performed by running the shell script `main_dicom_conv_batchautom.sh`, which accesses the `settings.py` file and performs the conversion according to the specified parameters.

+ **Step 0:**
    + Set up miniforge, so you can use the conda (or mamba) package manager (you can follow the instructions in [Setting up Conda](https://wiki.cbs.mpg.de/spaces/CBSNP/pages/158105663/Setting+up+Conda))

+ **Step 1:**
    + connect to a compute server via ssh 
    ```
    getserver -l	# show a list of available compute servers
    ssh maki 		# connect to maki (or any other compute server)
    ```

+ **Step 2:**
    + Activate a virtual environment containing a recent python version. You can use the provided `bidsme_env.yml` to create an environment suited for this and later steps of the processing.
    ```
    # conda env create -f bidsme_env.yml   # create environment from the yaml-file if you haven't done this yet
    conda activate env_name   # activate environment
    ```

+ **Step 3:**
    + Access the `settings.py` file and adjust the parameters to your specific needs.
        + Specify path pairs for as many sessions as you want, starting at 1. 
        + The number of specified sessions MUST coincide with the `number_of_paths` variable.
    ``` 
    run_dicom_conv=1  # needs to be set to 1
    number_of_paths=2  # maximum number of directories that need to be converted
    path_to_dcm1="path/to/dcm"  # specify input folder (DICOM data)
    path_to_nii1="path/to/nii"  # specify output folder (NIfTI data)

    hMRI_dcmConv_excl="noddi"   # specify a string → all file names that contain this string are skipped by the SPM DICOM Import and converted using dcm2niix instead
    ```

+ **Step 4:**
    + Access the Matlab file `call_dicom_conversion.m` and adjust the paths where SPM, hMRI-toolbox, and the dicom_import functions are stored.
    ```
    addpath('/data/u_kuegler_software/git/spm12')
    addpath('/data/u_kuegler_software/git/hMRI-toolbox')
    addpath('/data/u_kuegler_software/git/MPM_bidsification/spm_dicom_import')
    ```

    + This function is called by the main script and runs the DICOM import in MATLAB.
        + It uses the MATLAB environment version `9.16` but other versions may also work. This is specified in `main_dicom_conv_batchautom.sh` when calling the `call_dicom_conversion` function. 

+ **Step 5:**
    + Run the conversion from the CLI by navigating to the local directory of the **MPM_bidsification** repository and calling the `main_dicom_conv_batchautom.sh` script.
    ```
    cd path/to/MPM_bidsification
    ./main_dicom_conv_batchautom.sh
    ```

> **Hint:**<br>
Ilona Lipp's DICOM import script performs several checks. Sometimes it gets stuck at a specific point and repeats the import of the failing directory indefinitely. If this happens, you can try the version of the function that skips all the checks by setting the `check_results` parameter in the `call_dicom_conversion` function call to `false`. (This is not thoroughly tested and I would recommend to keep this parameter set to `true`.)


#### Full dcm2niix conversion (alternative)
To convert all DICOM data using **dcm2niix** instead of the SPM DICOM Import, you can use the script `main_dcm2niix_conversion.sh` similar as described above. The script excludes files matching a certain string (specified in `settings.py`) from the SPM DICOM Import and converts them using dcm2niix. This was originally implemented to convert diffusion MRI data, as the SPM DICOM Import does not create the necessary _.bvec_ and _.bval_ files for diffusion data sets. However, if you want to convert **all** DICOM data using dcm2niix, you can specify a string that is present in **all** file names (e.g., "_"). <br>

> More information on *dcm2niix* usage can be found in the [dcm2niix documentation](https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#General_Usage).


## File description

+ `spm_dicom_import/` – scripts adapted from the [postmortembrain-mpm](https://github.com/IlonaLipp/postmortembrain-mpm) repository (Author: Ilona Lipp)
    + `convert_dicoms_to_nifti.m` – main function called for DICOM-to-NIfTI conversion (using SPM DICOM Import)
    + `convert_dicoms_to_nifti_no_check.m` – adjusted function of the one above that skips checks during the process (use with care: quicker but hard to detect if files were skipped)
    + `check_if_all_nifti_files_have_same_dimensions.m` – helper function
    + `convert_dir_output_to_cell_structure.m` – helper function
+ `call_dicom_conversion.m` – script that sets the paths in the MATLAB instance and calls the DICOM Import script
+ `main_dicom_conv_batchautom.sh` – call the DICOM-to-NIfTI conversion for a batch of files (inherits the paths to each file and to the output directory from the `settings.py`)
+ `main_dicom_conv.sh` *(deprecated)* – call the DICOM-to-NIfTI conversion for a single file (paths as arguments)
+ `nii_dtibatch.m` *(not relevant for the bidsification)* – script to check the `.bvec` and `.bval` files created by *dcm2niix* from diffusion data (found in the [dcm2niix documentation](https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#Diffusion_Tensor_Imaging), [link to the script on Github](https://github.com/rordenlab/spmScripts/blob/master/nii_dtibatch.m))
+ `settings.py` – specify paths and parameters for DICOM-to-NIfTI conversion using `main_dicom_conv_batchautom.sh`

## ToDos
+ Replace the current DICOM Import implementation by a more robust solution. (possibly just the standard import code extracted from the Batch editor)
+ This implementation is preliminary but it works and it is not needed a lot. However, the plan is to recreate the main script in python and to refine the settings/config file to be more self explanatory.
+ Paths in `call_dicom_conversion.m` should be adjusted in the config file, not in the script
+ implement a toggle to either use DICOM Import/dcm2niix OR just dcm2niix
+ directory structure needs to be specified manually --> write a short script to automatically create the top-level directories (bids, source, temp, id_files)