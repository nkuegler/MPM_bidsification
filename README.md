# Bidsification + Analysis of IronSleep Sessions

<mark>**--- currently under development ---**<mark>

This pipeline is meant to be used as a start-to-finish data processing and analysis tool. It was originally created for the IronSleep project but can be adjusted to work on similar data that need to be processed the same way.

## Pipeline steps
1. DICOM to NIfTI conversion
2. Bidsification of the NIfTI data
3. SPM **--- not yet implemented ---**
    + hMRI toolbox denoising module *(alternatively nighres denoising?)*
    + SPM segmentation
    + hMRI toolbox processing module (maps creation) *(account for pTX mapping if available)*
4. MASSP parcellation module **--- not yet implemented ---**
5. Data extraction **--- not yet implemented ---**


**Additional functionalities that are planned to be included**
- $T_2$ data analysis *(?)*
- LORAKS reconstruction of MPMs *(probably as optional step 0)*
- generation of QSM maps from combined MPM phase data

<br>

> It is planned to run the pipeline by calling a single script after specifying the necessary paths, parameters, and which steps to be run in the settings file (or better config file).


## Requirements
The code in this repository leverages different functions of previous work. Before starting the process, several toolboxes/packages/repositories must be installed and dependencies must be set correctly. 

The hMRI toolbox is part of SPM. Therefore the SPM repository and the hMRI toolbox repository need to be cloned and the dependencies adjusted accordingly. Please check out the [hMRI toolbox Wiki](https://github.com/hMRI-group/hMRI-toolbox/wiki/GetStarted) for more information on the installation. You do not need to add paths in MATLAB, as this is done by the `call_dicom_conversion.m`.

Bidsification is done using [Bidsme](https://github.com/CyclotronResearchCentre/bidsme) (curtesy of Nikita Beliy). For using this package, you need to install it via pip. Check out Nikita's Github for more information on this. I added my (cluttered) mamba `bidsme_environment.yaml` in the supplementary directory of this repository.


## Using the scripts 
Before running the main script, it is necessary to adjust the `settings.py` file to fit your needs. 

### Step 1: DICOM to NIfTI
To run the first step of the pipeline, `run_dicom_conv` needs to be set to `1`, otherwise set it to `0`.
Specify `path_to_dcmX` as the path to your DICOM data and `path_to_niiX` as the path to your NIfTI data (output folder) for as many sessions as you want.
The variable `number_of_paths` must match the number of specified sessions. 

In general, the DICOM to NIfTI conversion is performed using the DICOM import of the hMRI toolbox. However, this is not optimal for diffusion data, as it does not convert it according to BIDS specification and also lacks the ability to create the necessary `.bvec` and `.bval` files. Therefore, diffusion data (or more specifically) data that contains the string `"noddi"` (as specified as `hMRI_dcmConv_excl` in `settings.py`) is ignored in the DICOM import, and automatically converted thereafter by `dcm2niix`. 
> Hint: For the conversion of the hMRI DICOM import, all folders are neglected where there is already data present in the specified NIfTI directory, that have the series number `99` or that contain the string `[`.

You can run the main script by running the following CLI command:
`cd path/to/repository
bash main_dicom_conv_batchautom.sh`

### Step 2: Data Bidsification
Bidsme is used for converting the NIfTI data in a BIDS-conform structure. Due to testing purposes, this process is currently done in a Jupyter Notebook (hence, the installation of Jupyter lab). 

First, you have to specify `DATASET_PATH`, `SOURCE_PATH`, `PREPARED_PATH`, and `BIDSIFIED_PATH` **(1)**. For my testing, I used the following file structure and the script `Configuration/00_set_paths.py` but this will be adjusted in the future:

```
DATASET_PATH
│
└───bids
└───prepared
└───source
```

Next, Bidsme and the logger object will be initialized **(2)**. 

In step **(3)**, the data is prepared for the bidsification. In the `bidsme.prepare` command, you need to define, where Bidsme can find NIfTI files. Therefore, the first filtering of unneeded data can be done during this step. Additionally, a custom plugin `plugins_bidsme/plugin_prepare_nk.py` is passed to the command. This plugin adjusts the subject and session names according to previously created `.csv` files present in `PREPARED_PATH/id_info` or as increasing integers starting at 001. In case of the latter, the `id_files` are created during the renaming process. Secondly, the plugin moves the `bvec` and `bval` files to the according location if diffusion data is present in the current session. 

The creation of the `bidsmap.yaml` in step **(4)** is presumably the most tedious step of the bidsification. When running the `bidsme.mapper` command, the `PREPARED_PATH` is scanned and a `bidsmap.yaml` file is created in `BIDSIFIED_PATH/code/bidsme` or, if already present, extended. This mapping file creation is an iterative process. Open the directory in a code or text editor (I use VS Code) and iteratively adjust the mapping file. Each time the `bidsme.mapper` command is run, it will stop at some point and raise warnings and/or errors. According to the error message, you need to adjust the mapping file and re-run the command. Usually, bidsme will extend the mapping file with template entries that you just need to fill out. However, sometimes you need to manually specify which template should be used. You can find information on how to perform the mapping in the included `02-basic-mapping.ipynb` notebook, which is part of the bidsme basic tutorial, or in the [documentation](https://github.com/CyclotronResearchCentre/bidsme/blob/dev/doc/creating_map.md). Repeat this step until there are no warnings and errors when running `bidsme.mapper`. The plugin `plugins_bidsme/plugin_bidsify_nk.py` is used to create custom fields that need to be included in the bidsmap.

Now you can run step **(5)** of the notebook, which is the bidsification of the data. There should be no warnings or errors raised during the bidsification (I still get warnings due to a missing `README.md` and `dataset_description.json` that need to be included in a BIDS-conform dataset. Creating those should not be too difficult, I just haven't done it yet). 


## Visualization of current script structure
![image](docs/status_repo_2024-11-12.png)


## Acknowledgements
The pipeline re-uses software from several different researchers. 
- Nikita Beliy
- Mikhail Zubkov
- Ilona Lipp

This list will be extended.



# Added functionality but needs to be described in README
+ Bidsification of LORAKS data best when done after bidsification of DICOMS
    + if there is no bidsified DICOM data, the LORAKS bidsification will work, but there is no information on shim current consistency
+ Bidsification of LORAKS data only works when a corresponding BIDS directory is found (can be empty):
    + the following lines need to be commented out in the `plugin_prepare_loraks_nk.py` to work without original BIDS directory
        ```
        if not os.path.exists(corresponding_bids_data_path):
            raise exceptions.InitEPError(f"Corresponding BIDS directory not found at {corresponding_bids_data_path}")
        ```

