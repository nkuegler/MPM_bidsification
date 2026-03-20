#!/usr/bin/env python
# coding: utf-8

# ## 0 - Dataset installation

# This tutorial is based on syntetic MRI dataset, which can be cloned
# from GitLab:
# ```bash
# cd <work directory>
# git clone https://gitlab.uliege.be/CyclotronResearchCentre/Public/bidstools/bidsme/bidsme_example
# cd bidsme_example/example1
# ```
# 
# The example dataset is a lightweighted dummy MRI dataset of 4 subjects and 3 sessions.
# In the `example1/` folder there are four subfolders:

# - `source`, containing the raw, unbidsified dataset
# - `renamed`, an empty folder that will contain the prepared dataset
# - `bids`, an empty folder that will contain the bidsified dataset
# - `resources`, containing all needed configurations and plugins needed to bidfify this dataset
# 
# > You can use your own dataset, but all commands in the tutorial must be adapted to it!

# ## 1 - Path definitions

# We will pass regularly the different sub-folders of the example dataset,
# so for convinience we will define these paths as variables and
# will put into a script.

# Next is to define paths to the dataset we will use as an
# example:

# In[3]:


DATASET_PATH = "/data/pt_02262/data/temp/krohn_test/"


# If you follow the `bidsme-example/example_1` dataset,
# the following paths can be generated automatically.
# 
#  - `SOURCE_PATH` -- Path to source dataset, which contains raw images.
#  - `PREPARED_PATH` -- Path where we will store intermediate (prepared) dataset.
#  - `BIDSIFIED_PATH` -- Path where we will store bidsdsified dataset.
#  - `RESOURCES_PATH` -- Path where all configuration files needed for bidsification are stored. We will recreate them, but you can check them for reference there.
#  - `MAP_FILE` -- Path to `bidsmap.yaml` file, that will define how we will bidsify dataset.
# 
# Otherwise you should redefine them to point to your dataset.

# In[4]:


import os


# In[5]:


SOURCE_PATH = os.path.join(DATASET_PATH, "source")
PREPARED_PATH = os.path.join(DATASET_PATH, "prepared")
BIDSIFIED_PATH = os.path.join(DATASET_PATH, "bids")
# RESOURCES_PATH = os.path.join(DATASET_PATH, "example1", "resources")


# The following cells will verify if the defined directories exist:

# In[7]:


print("Dataset path:", os.path.isdir(DATASET_PATH))
print("Source path:", os.path.isdir(SOURCE_PATH))
print("Prepared path:", os.path.isdir(PREPARED_PATH))
print("Bidsified path:", os.path.isdir(BIDSIFIED_PATH))
# print("Resources path:", os.path.isdir(RESOURCES_PATH))


# If you see some `False`, please recheck the paths.

# ## 2 - Exporting paths to script

# Now, we will export this notebook as a script, and place it into `MRI_tutorial/Configuration`
# folder:

# In **Jupyter-lab**:
# 
# >To do so, you need to go to `File ->Save and export Notebook as -> Executable script`.
# 
# In **Jupyter-notebook**:
# >Go to the menu `File -> Download as -> Python(.py)`.
# 
# If your browser offers the opportunity to save file in a given directory,
# save it in the `Configurations` folder in the root directory of tutorials.
# Overwise, move the file from `Downloads` folder to `MRI_tutorial/Configuration`.
# 
# You will need to change the the generated python script only if you move
# tutorial dataset into different place.

# Obviously, you can create the script directly, but be sure to define all the paths above!

# In[ ]:




