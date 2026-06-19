# LORAKS 
import os
from pathlib import Path
import bidsme

from test_bidsify import subjects

# RESOURCES_PATH = os.path.join(DATASET_PATH, "example1", "resources")


# DATASET_PATH = Path("/data/pt_02262/data/liege_data")
DATASET_PATH = Path("/data/pt_03187/data/in_vivo/")
# DATASET_PATH = Path("/data/pt_03068/data/in_vivo")

SOURCE_PATH = DATASET_PATH / "source"
PREPARED_PATH = DATASET_PATH / "temp" / "LORAKS"
BIDSIFIED_PATH = DATASET_PATH / "bids" / "derivatives" / "LORAKS"
# RESOURCES_PATH = BIDSIFIED_PATH / "code" / "resources"
WORKING_DIR = Path.cwd()

print("Dataset path:", DATASET_PATH.is_dir())
print("Source path:", SOURCE_PATH.is_dir())
print("Prepared path:", PREPARED_PATH.is_dir())
print("Bidsified path:", BIDSIFIED_PATH.is_dir())
# print("Resources path:", RESOURCES_PATH.is_dir())
print("Working directory:", WORKING_DIR)

logger = bidsme.init()

logger.setLevel("INFO")
bidsme.prepare(str(SOURCE_PATH), str(PREPARED_PATH),
               data_dirs={"nii_loraks_recon":"MRI",
                          # "nii_loraks_recon/*":"MRI",
                          },
               plugin_file = str(WORKING_DIR / "plugins_bidsme" / "plugin_prepare_auto_nk.py"),
               # plugin_file = str(WORKING_DIR / "plugins_bidsme" / "liege_data_IronSleep" / "plugin_prepare_loraks_liegeData_nk.py"),
               part_template = str(WORKING_DIR / "supplementary" / "table_templates" / "participants_nk.json"),
               plugin_opt = {"sessions_tsv_template": str(WORKING_DIR / "supplementary" / "table_templates" / "sessions_nk.json"), "include_smaps": False},
               # sub_skip_dir=True,
               sub_list=["sub-004","sub-008","sub-019"]  # only run on specified subjects (must be specified in BIDS notation)
              )
bidsme.tools.info.reporterrors(logger)
bidsme.tools.info.reseterrors(logger)

PLUGIN_BIDS = WORKING_DIR / "plugins_bidsme" / "plugin_prepare_unified_patched_FIXED.py"
# PLUGIN_BIDS = WORKING_DIR / "plugins_bidsme" / "liege_data_IronSleep" / "plugin_bidsify_loraks_liegeData_nk.py"

bidsme.mapper(str(PREPARED_PATH), str(BIDSIFIED_PATH), plugin_file=str(PLUGIN_BIDS),
              plugin_opt={"bidsmap_step": True, "include_smaps": False},
              sub_list=["sub-004","sub-008","sub-019"],
              # sub_skip_tsv=True,
              )
bidsme.tools.info.reporterrors(logger)
bidsme.tools.info.reseterrors(logger)

MAP_FILE = str(BIDSIFIED_PATH / "code" / "bidsme" / "bidsmap.yaml")
PLUGIN_FILE_BIDS = str(WORKING_DIR / "plugins_bidsme" / "plugin_bidsify_auto_nk_rewritten_FIXED.py")
# PLUGIN_FILE_BIDS = WORKING_DIR / "plugins_bidsme" / "liege_data_IronSleep" / "plugin_bidsify_loraks_liegeData_nk.py"

import subprocess
subjets=["sub-004","sub-008","sub-019"]
subprocess.run([
    "bidsme", "bidsify",
    str(PREPARED_PATH),
    str(BIDSIFIED_PATH),
    "-b", str(MAP_FILE),
    "--plugin", str(PLUGIN_FILE_BIDS),
    "--participants", *subjets,
], check=True)# !bidsme bidsify $PREPARED_PATH $BIDSIFIED_PATH -b $MAP_FILE --plugin $PLUGIN_FILE_BIDS --participants 'sub-001'
# !bidsme bidsify $PREPARED_PATH $BIDSIFIED_PATH -b $MAP_FILE --plugin $PLUGIN_FILE_BIDS --skip-existing