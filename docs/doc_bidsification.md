# Documentation: Bidsification of the MRI data

This page describes the bidsification of the MRI acquisition data in NIfTI format (.nii). There are settings implemented to bidsify both the NIfTIs created from the scanner-reconstructed DICOMs and the NIfTIs reconstructed from the raw MRI data using LORAKS. 

> Brain Imaging Data Structure (BIDS) is a standardized way of organizing Neuroimaging data. It makes recommendations for the directory structure, file naming, and metadata storage.<br>
> The standard includes guidelines for multiple imaging techniques. This guide is restricted to MRI data for now.<br>
> For more information on BIDS, please refer to [their documentation](https://bids-specification.readthedocs.io/en/stable/index.html). It is difficult to navigate but the search function is your friend. There are still some inconsistencies in the standard, making exact definitions difficult in some cases.<br>

The scripts that are described on this page are part of the **MPM_bidsification** repository ([Github](https://github.com/IronSleep/MPM_bidsification), [Gitlab](https://gitlab.gwdg.de/cbs-neurophy/bidsification_mpm)). Feel free to clone or fork the repository. If there are problems regarding the permissions, [send me an e-mail](mailto:kuegler@cbs.mpg.de?subject=Permissions%20missing%20MPM_bidsification) (kuegler@cbs.mpg.de) or a message on Minerva (user: kuegler).


## Usage

The Bidsification of the data is performed using *Bidsme*, an open-source tool created by Nikita Beliy (University of Liege, Belgium). It is an all-in-one tool for the re-naming and re-structuring the original data files and extracts and formats the necessary metadata. It is fully customizable due to the option of including custom plugins. Instead of strictly imposing the BIDS structure, Bidsme allows the user to fully configure how the data set will be organized and what metadata will be included, providing maximum flexibility even beyond the limitations of the BIDS standard.<br>

According to the BIDS recommendations, the data is structured in subject directories, which contain a separate directory for each session.<br>

The names of the NIfTI files adhere to the following structure : `subject - session - different entities describing the data - suffix of the acquisition - .nii` <br>
The data files are easily identifiable by their unique names due to the explicit definition of entities by the BIDS standard. <br>
Each .nii file is accompanied by a sidecar JSON file with the same name, which contains all the important metadata. <br>

> The Bidsification code is currently organized in Jupyter notebooks with supplementary python scripts. As *Bidsme* can be used both as Python package and as command line tool, the necessary functions will be called from the command line in the final deployment of the pipeline. However, for development and debugging reasons, it is convenient to use Jupyter notebooks. 


> Hint:
> It is recommended to first bidsify the DICOM-derived data, and then follow with the LORAKS-reconstructed files. Bidsification of just LORAKS data still requires a specific folder structure and possibly some manual adjustments, which is not thoroughly tested.


### Necessary software/repositories

+ **MPM_bidsification**
    + The versions on the [Neurophysics Gitlab](https://gitlab.gwdg.de/cbs-neurophy/bidsification_mpm) and the [IronSleep Github](https://github.com/IronSleep/MPM_bidsification) are identical (synced). However, access to both repositories is restricted. [Reach out](mailto:kuegler@cbs.mpg.de?subject=Permissions%20missing%20MPM_bidsification) if you want to access the code.
+ **Bidsme**
    + *Bidsme* is freely available on [Github](https://github.com/CyclotronResearchCentre/bidsme/tree/dev) and [Gitlab](https://gitlab.uliege.be/CyclotronResearchCentre/Public/bidstools/bidsme/bidsme). 
    + You **don't** need to manually install *Bidsme*. The **MPM_bidsification** repository provides an environment file `bidsme_env.yml` in the `supplementary/` directory that you can use to create a proper mamba/conda environment including *Bidsme* and all its necessary dependencies. This environment may also be used for the previous steps of the pipeline. How to create the environment from the YAML file is described in the steps below.
    + *Alternatively, you can find [instructions for installing Bidsme](https://github.com/CyclotronResearchCentre/bidsme/blob/dev/INSTALLATION.md) to your virtual environment. Bidsme can be installed directly using pip, including the necessary dependencies.*
+ **dcm2niix**
    + You can either clone the [Github repository](https://github.com/rordenlab/dcm2niix) or download the [MRIcroGL viewer](https://www.nitrc.org/projects/mricrogl/) which includes dcm2niix as graphical interface.
    + other install options are by using conda/mamba, pip, apt-get, or brew (see the instructions in the Github repository)
    + [documentation of dcm2niix](https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#General_Usage) (includes information on bvec & bval file creation in the DTI section)


### How to run the Bidsification

The bidsification is performed by successively running the code blocks in `bidsify_IronSleep.ipynb`. For the LORAKS-reconstructed data, use `bidsify_IronSleep_loraks.ipynb`.<br>
The scripts will access different files in the `plugins_bidsme/` and the `supplementary/` directories to perform the different steps of the Bidsification process. All important files are explained in the [**File description**](#file-description-mpm_bidsification-repository) section later on this page.

> Hint:<br>
> Stick to main branch of the repository for now. The use cases of the other branch(es) are described later.

+ **Step 0:**
    + Set up miniforge, so you can use the conda or mamba package manager (you can follow the instructions in [Setting up Conda](https://wiki.cbs.mpg.de/spaces/CBSNP/pages/158105663/Setting+up+Conda)).

+ **Step 1:**
    + Create an appropriate virtual environment from the provided `bidsme_env.yml` if you haven't done this in a previous step.
    + Make sure that you don't already have a conda/mamba environment with the name `bidsme_env`. You only need to create the environment once.
    + ```
      # cd path/to/MPM_bidsification 					 # navigate to the local clone of the repository
      # mamba env create -f supplementary/bidsme_env.yml # create a conda/mamba environment from the yaml-file in the supplementary directory
      mamba env list									 # check the list of environments for the newly created one "bidsme_env"
      ```

+ **Step 2:**
    + Organize your data as described in [Preparation: Data structure](https://wiki.cbs.mpg.de/spaces/~kuegler/pages/214368262/Preparation+Data+structure) if you haven't done this already.
    + Your project directory must include a `bids/`, `source/`, and `temp/` directory. The `id_info/` directory will be created during the Bidsification if it does not exist yet. However, if you plan to manually define the mapping of original to BIDS-conform IDs, you need to create it manually before running the Bidsification.
    + The data in the `source/` directory must be organized in descending subject and session directories as described on the Data structure page. Each session should contain both a `nii/` directory (NIfTIs from DICOM data) and a `nii_loraks_recon/` directory (LORAKS-reconstructed NIfTIs). Different names of those directories require manual adjustments in the code. 

+ **Step 3:**
    + Connect to a compute server via ssh.
    + ```
      getserver -l	# show a list of available compute servers
      ssh maki 		# connect to maki, manati, or any other compute server
      ```

+ **Step 4:**
    + Activate the virtual environment containing *Bidsme* and all the necessary dependencies.
    + ```
      mamba activate bidsme_env   # activate mamba/conda environment
      ```

+ **Step 5:**
    + Access the `bidsify_IronSleep.ipynb` and adjust the paths to your needs (1. Section in the notebook).
    + ```
      DATASET_PATH = "/path/to/your/project/directory"
      # adjust the variables SOURCE_PATH, PREPARED_PATH, and BIDSIFIED_PATH if you diverged from the directory naming recommendations
      ```
    + After this, successively execute the cells in the notebook. The different steps are described below.

+ **Step 6: `bidsme.prepare`**

    + In the `bidsify_IronSleep.ipynb`, run the cell containing the `bidsme.prepare` command (3. Section in the notebook).
    + This function successively steps through the different sessions of the different subjects present in the `source/` directory, copies the data and organizes it in a BIDS-conform folder structure in the `temp/` directory. This is just a preparation and **not** the actual bidsification yet.
    + You have to specify in the `bidsme.prepare` command, where *Bidsme* can find the NIfTI files of the sequences. You have the option to exclude data from this step which will also exclude it from the bidsification in the following steps. However, make sure that you don't miss important data (*e.g.*, if you use the provided scripts but your sequence names vary from the specified ones).
    + You can pass a custom plugin to the command to apply custom modifications (*e.g.*, `plugin_prepare_nk.py` in the `plugins_bidsme/` directory). 
        + This plugin adjusts subject and session names according to the previously created `.csv` files in the `id_info/` directory (forces a specific naming onto the subjects/sessions). If there are no "ID-files" or not even an `id_info/` directory, the subjects and sessions are numbered with increasing integers (subjects: 3-digits, sessions: 2-digits) and the mapping from their original IDs to the BIDS-conform IDs is documented in newly created `.csv` files in the `id_info/` directory.
        + Additionally, it moves the `.bvec` and `.bval` files of the diffusion-weighted data to the according sessions in the `temp/` directory, as this is not done by *Bidsme*. 
    + The "participants" template (.json) passed to the command defines the structure of the `participants.tsv` file. The creation of the `sub-XXX_sessions.tsv` is not implemented in *Bidsme* and is therefore also handled by the custom plugin `plugin_prepare_nk.py`.
    + For other arguments of the command (*e.g.*, which subset of subjects to run on if not all), please refer to the help command or the Bidsme documentation.
    + ```
      bidsme.prepare(SOURCE_PATH, PREPARED_PATH, 
                     data_dirs={"nii/*":"MRI",
						         ... },
                     plugin_file="/path/to/plugin_prepare.py",
                     part_template="/path/to/participants.json",
			         plugin_opt={"bool_val":True},      # pass variable to plugin
                     sub_list=['sub-002','sub-003']
                    )     
      ```
    > There are several sanity checks implemented in the plugin. For example, the *Bidsme* logger raises a warning if the shim currents in the different MPM sequences and the TB1AFI acquisition are not constant. Such inconsistencies would probably render the data unusable. However, the data is still bidsified but this warning creates a WARNING file in the corresponding session in the `bids/` directory and notes this problem in the `sub-XXX_sessions.tsv`. *(Warnings don't stop the execution of the function.)*

+ **Step 7: `bidsme.mapper`**

    + In the `bidsify_IronSleep.ipynb`, run the cell containing the `bidsme.mapper` command (4. Section in the notebook).
    + This function creates the `bidsmap.yaml` file. This structured file defines the actual names of the bidsified data and specifies which metadata of the sidecar JSON files in the `temp/` directory will be transferred to the sidecar JSON files of the bidsified data. The mapping information is stored as key-value pairs in human-readable, widely supported YAML files.
        + By default, the file is created in `BIDSIFIED_PATH/code/bidsme/bidsmap.yaml` or, if already present, scanned and extended. 
    + **You can skip this step if you are bidsifying data of the IronSleep project as you can use the `example_bidsmap_MPM.yaml` provided in `supplementary/bidsmaps/`.**
    + The creation of the mapping file is an iterative process. Each time the `bidsme.mapper` command is run, it will successively analyze the data in the `temp/` directory. Once it comes across a file with unknown attributes (*e.g.*, `ProtocolName`), it will stop and raise an error. This error can be resolved by adding a new element to the mapping file with this specific `ProtocolName` in the attribute section. In many cases, *Bidsme* will extend the mapping file with template entries, showing you, which fields need to be specified. If not, you can specify manually which template to use by adding a "blank" element, specify only the `model` and `suffix` fields, and add `template: true`. If you now run the `bidsme.mapper` command again, the blank element will be populated with empty fields from the template.
        + Read the error message carefully as it often provides good instructions on how to resolve the error(s) or warning(s).
        + You can find more information on how to create a proper Bidsmap in the [documentation in the Bidsme Github repository](https://github.com/CyclotronResearchCentre/bidsme/blob/dev/doc/creating_map.md) (or alternatively in the [Jupyter Notebooks of the bidsme tutorial](https://github.com/CyclotronResearchCentre/bidsme_tutorial)).

    > The naming schema and sidecar JSON fields for a given modality (in this case `MRI`) are defined in `$BIDSME_INSTALLATION_PATH/bidsme/Modules/MRI/_MRI.py`. The list of entities is stored in modalities dictionary. For example, if an image belongs to `anat`, *Bidsme* will load the list of entities from `modalities["anat"]`. The optional `model` field in the bidsmap can force *Bidsme* to use a different list of entities from the modalities dictionary.

    + **I recommend to open the created `bidsmap.yaml` in a code editor (*e.g.*, VS Code) and iteratively re-run the cell and adjust the mapping file.**
        + Repeat this process until the command doesn't raise any warnings or errors.
        + This process can be very tedious and many features are not well documented. Feel free to reach out if you need help ([kuegler@cbs.mpg.de](mailto:kuegler@cbs.mpg.de?subject=Help%20with%20MPM_bidsification) or Minerva messenger user: kuegler).
    + The good thing is that the `bidsmap.yaml` has to be **created only once** including all the different `ProtocolNames`. If every session follows the same protocol, you specify the Bidsmap for one session and, thereafter, use it to bidsify your whole data set.
    + The custom plugin `plugin_bidsify_nk.py` creates variables that are used to populate the `bidsmap.yaml` with custom values. The plugin is available in the `plugins_bidsme/` directory in the **MPM_bidsification** repository.
    + ```
      PLUGIN_BIDS = "/path/to/plugin_bidsify.py"
      bidsme.mapper(PREPARED_PATH, BIDSIFIED_PATH, plugin_file=PLUGIN_BIDS,
                    plugin_opt={"bidsmap_step": True},  # pass variable bidsmap_step to plugin
                    sub_list=['sub-002','sub-003']
                   )
      ```
    > The `bidsme.mapper` command stops when the logger raises a warning (`bidsme.prepare` only stops at errors). Therefore, the custom-designed shim current check described in step 6 will stop the execution when shim current inconsistencies are detected. If this happens, this sanity check has to be commented out during the bidsmap creation. This has no influence on the `bidsmap.yaml` but is useful in the preparation and bidsification steps. When creating the Bidsmap for LORAKS-reconstructed data, warnings are raised due to the absence of some standard fields in the sidecar JSON files. These warnings terminate the execution of the command. You can find more on this problem in the *very important note* in [Bidsification of LORAKS-reconstructed data](#bidsification-of-loraks-reconstructed-data).

+ **Step 8: `bidsme bidsify`**

    + In the `bidsify_IronSleep.ipynb`, run the cell containing the `!bidsme bidsify` command (5. Section in the notebook).
        + The `!` (exclamation mark) indicates a CLI command called from the Jupyter notebook.
    + This function performs the actual bidsification of the data in the `temp/` directory according to the specifications in the `bidsmap.yaml` file. The bidsified data is written to the `bids/` directory.
        + If everything worked well in the previous two steps, no warnings or errors should be raised during the bidsification.
        + Two warnings could arise if you did not include a `README.md` and `dataset_description.json` in the `bids/` directory. Those files are required to make the data set BIDS-conform. You can find templates for each of them in the `supplementary/` directory in the **MPM_bidsification** repository. Please refer to [IronSleep: Data storage structure](https://wiki.cbs.mpg.de/spaces/~kuegler/pages/214368339/IronSleep+Data+storage+structure) or the [BIDS documentation](https://bids-specification.readthedocs.io/en/stable/) for more information about these files.
    + You can use additional flags with the command to specify which subjects/sessions are included in (or excluded from) the bidsification. 
        + Find more information by running `bidsme bidsify --help` in the CLI. (Make sure, that the `bidsme_env` environment is activated. Otherwise *Bidsme* is not available.)
    + The same plugin `plugin_bidsify_nk.py` as in the previous step is used.
    + Everything described in the previous two steps is now applied to the bidsification and the whole bidsified data set is stored in the `bids/` directory.
    + ```
      MAP_FILE = os.path.join(BIDSIFIED_PATH, "code/bidsme/bidsmap.yaml")
      PLUGIN_FILE_BIDS = "/path/to/plugin_bidsify.py"
      
      !bidsme bidsify $PREPARED_PATH $BIDSIFIED_PATH -b $MAP_FILE --plugin $PLUGIN_FILE_BIDS -o bidsmap_step=False --participants 'sub-002'
      ```
    + It is possible to pass options to the plugins in the different *Bidsme* commands. As this is not quite clear in `bidsme bidsify --help`, passing options to plugins is done by `-o Name1=Value1 Name2=Value2 ...` (no brackets, no commas).
        + Be careful when you use this flag, as the variable type is not always correctly recognized by the Python script when calling the `bidsme bidsify` command from the CLI. <br>
        (*e.g.*, `False` was recognized as string instead of boolean, which causes conditional statements to consider the variable as `True`.)
        + A fix was implemented for arguments with boolean values but it may not cover all possible cases. 


### Additional functionalities in the repository

#### Bidsification of LORAKS-reconstructed data
The Bidsification of the LORAKS-reconstructed data is also implemented in the repository.<br>

As the metadata of these files varies vastly from the DICOM-imported NIfTIs, I created a separate set of plugins and a different bidsmap for this (`*_loraks*` in the file name).<br>

Please use the `bidsify_IronSleep_loraks.ipynb` for the bidsification of the LORAKS-reconstructed NIfTIs. The steps above can be followed equivalently.<br>

The bidsified LORAKS-reconstructed data is stored in `PROJECT_DIR/bids/derivatives/LORAKS/`. This directory is created during the bidsification. If you alter the folder structure, you need to adjust the plugin:
```
### the following lines need to be commented out in the `plugin_prepare_loraks_nk.py` to work without original BIDS directory

if not os.path.exists(corresponding_bids_data_path):
	raise exceptions.InitEPError(f"Corresponding BIDS directory not found at {corresponding_bids_data_path}")
```
> *Disclaimer: There is no guarantee that the bidsification will work properly when you adjust the folder structure.*


As mentioned before, the Bidsification of the LORAKS-reconstructed data should be performed AFTER the Bidsification of the DICOM-imported data. If there is no bidsified DICOM data, the LORAKS bidsification should still work but there won't be any information on shim current consistency available. This case was also not thoroughly tested, so there may be a few bugs.


> <font color="red">**Very important note:**</font><br>
>
> <font color="red">During the preparation, WARNINGS will be raised by the logger, claiming that Bidsme was *"Unable to get recording Id for file ..."*. These warnings can be ignored, as they were addressed but the logger output cannot be removed without destroying its functionality. Not raising any warnings would potentially lead to overlooking a different, more severe issue.</font><br>
>
> <font color="red">The Bidsmap creation step will raise the same WARNINGS, causing this step to crash early. Until this is fixed, you need to rely on your experience on how to create a proper Bidsmap without the help of this function. If you made a mistake in the `bidsmap.yaml`, the `bidsme bidsify` command will raise an error or you will find the mistake in the resulting sidecar JSON files in the bidsified data (*e.g.*, missing or falsely populated fields). </font><br>
>
> <font color="red">The `bidsme bidsify` command will also raise the same WARNINGS but the execution will not stop. Please also ignore these warnings as they were addressed but the logger output remains.</font><br>



## File description (**MPM_bidsification** repository)


