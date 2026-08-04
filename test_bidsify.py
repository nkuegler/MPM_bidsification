import os
from pathlib import Path
DATASET_PATH = Path("/data/pt_03187/data/in_vivo/")
# DATASET_PATH = Path("/data/pt_02262/data/TH_bids")

SOURCE_PATH = DATASET_PATH / "source"
PREPARED_PATH = DATASET_PATH / "temp"
BIDSIFIED_PATH = DATASET_PATH / "bids"
# RESOURCES_PATH = BIDSIFIED_PATH / "code" / "resources"
WORKING_DIR = Path.cwd()
print("Dataset path:", DATASET_PATH.is_dir())
print("Source path:", SOURCE_PATH.is_dir())
print("Prepared path:", PREPARED_PATH.is_dir())
print("Bidsified path:", BIDSIFIED_PATH.is_dir())
# print("Resources path:", RESOURCES_PATH.is_dir())
print("Working directory:", WORKING_DIR)

import bidsme
logger = bidsme.init()

logger.setLevel("INFO")
bidsme.prepare(str(SOURCE_PATH), str(PREPARED_PATH),
               data_dirs={
                   ### fine-grained directory specification example
                   # "nii/localizer*":"MRI",
                   # "nii/calc_shims_40mm*":"MRI",
                   # "nii/ernst_kp_mtflash3d_*_0p5_sag_*":"MRI",
                   # "nii/kp_afib1*":"MRI",
                   # "nii/AAHead*":"MRI",
                   # "nii/cmrr_noddi*":"MRI",
                   # "nii/t1w_kp_mtflash3d_*_0p6_*":"MRI",
                   # "nii/pdw_kp_mtflash3d_*_0p6_*":"MRI",
                   # "nii/mtw_kp_mtflash3d_*_0p6_*":"MRI",
                   # "nii/semc_js_res0p6_*":"MRI",
                   # "nii/JS_mod_semc*":"MRI",
                   # "nii/tfl_multiMTC*":"MRI",
                   # "nii/ke_gre_clearswi*":"MRI",

                   ### Traveling heads data
                   # "nii":"MRI", # files directly in the nii folder
                   #"nii/*":"MRI", # all file in subfolders of nii
                   "dcm2niix/*": "MRI",

                   ### Liege IronSleep data
                   # "nii/*":"MRI"

                   ### XALD data
                   #  "nii_dcm2niix/*":"MRI",
               },
               # plugin_file = str(WORKING_DIR / "plugins_bidsme" / "plugin_prepare_nk.py"),
               plugin_file=str(WORKING_DIR / "plugins_bidsme" / "plugin_prepare_nk.py"),
               # plugin_file = str(WORKING_DIR / "plugins_bidsme" / "TerraX_data" / "plugin_prepare_terrax_dcm2niix_nk.py"),
               part_template=str(WORKING_DIR / "supplementary" / "table_templates" / "participants_nk.json"),
               plugin_opt={"sessions_tsv_template": str(
                   WORKING_DIR / "supplementary" / "table_templates" / "sessions_nk.json")},
               sub_list=["sub-025"] # only run on specified subjects (must be specified in BIDS notation)
               )
bidsme.tools.info.reporterrors(logger)
bidsme.tools.info.reseterrors(logger)

#PLUGIN_BIDS = WORKING_DIR / "plugins_bidsme" / "plugin_biadsify_nk.py"
#PLUGIN_BIDS = WORKING_DIR / "plugins_bidsme" / "TerraX_data" / "plugin_bidsify_terrax_dcm2niix_nk.py"
PLUGIN_BIDS = WORKING_DIR/"plugins_bidsme/plugin_bidsify_auto_nk_rewritten_FIXED.py"

bidsme.mapper(str(PREPARED_PATH), str(BIDSIFIED_PATH), plugin_file=str(PLUGIN_BIDS),
              plugin_opt={"bidsmap_step": True},
              sub_list=["sub-025"],
              )
bidsme.tools.info.reporterrors(logger)
bidsme.tools.info.reseterrors(logger)

MAP_FILE = str(BIDSIFIED_PATH / "code" / "bidsme" / "bidsmap.yaml")
#PLUGIN_FILE_BIDS = str(WORKING_DIR / "plugins_bidsme" / "plugin_bidsify_nk.py")
PLUGIN_FILE_BIDS = str(WORKING_DIR / "plugins_bidsme" / "plugin_bidsify_auto_nk_rewritten_FIXED.py")

import subprocess
subjects = ["sub-025"]

subprocess.run([
    "bidsme", "bidsify",
    str(PREPARED_PATH),
    str(BIDSIFIED_PATH),
    "-b", str(MAP_FILE),
    "--plugin", str(PLUGIN_FILE_BIDS),
    "--participants",
    *subjects,
], check=False)