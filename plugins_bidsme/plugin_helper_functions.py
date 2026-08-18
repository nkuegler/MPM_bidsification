###############################################################################
# 
# This script contains helper functions for the implementation of custom plugins to be used with Bidsme.
# 
# Author: Niklas Kuegler
# Institution: Max Planck Institute for Cognitive and Brain Sciences, Leipzig, Germany


import pandas as pd
import numpy as np
import os
import re
import warnings
import shutil
import logging
from contextlib import contextmanager


def find_smap_modality(seq_list: list, current_index: int, search_direction: str = "forward") -> str:
    """
    Determines the modality of an SMAP sequence from a list of sequences.

    Sensitivity maps (SMAP) may be acquired either immediately before or after the
    intended modality (T1w, PDw, MTw). This function examines the elements in
    `seq_list` in the requested direction and checks for specific modality keywords
    ("t1w", "pdw", "mtw") in a case-insensitive manner. It returns the first
    matching modality found.

    Args:
        seq_list (list): A list of sequence names.
        current_index (int): The index of the current sequence in the list.
        search_direction (str): "forward" to search after the current index,
            or "backward" to search before it. Defaults to "forward".

    Returns:
        str: The modality of the sequence ("T1w", "PDw", or "MTw") if found,
                otherwise None.
    """

    direction = search_direction.casefold()
    if direction not in {"forward", "backward"}:
        raise ValueError("search_direction must be either 'forward' or 'backward'")

    if direction == "forward":
        indices = range(current_index + 1, len(seq_list))
    else:
        indices = range(current_index - 1, -1, -1)

    for i in indices:
        element = seq_list[i].casefold()  # Case-insensitive comparison

        # if the next element is also an smap, continue with the next element
        if "smap" in element:
            continue

        # Check for modalities
        if "t1w" in element:
            return "T1w"
        elif "pdw" in element:
            return "PDw"
        elif "mtw" in element:
            return "MTw"

    return None


def argument_to_bool(argument: str) -> bool:
    """
    Converts an argument (string or int) to a boolean value. Raises exception if the argument is not "True", "False", "true", "false", "1", "0", 1, or 0.
    If argument is already of type bool, it is returned as is.

    Args:
        argument (str or int): The argument to convert.
    Returns:"
        bool: The boolean value corresponding to the argument.
    """
    if isinstance(argument, bool):
        return argument
    
    else: 
        if argument.casefold()=="false" or argument==0 or argument=="0":
            return False
        elif argument.casefold()=="true" or argument==1 or argument=="1":
            return True
        else:
            return -1

@contextmanager
def temporary_logging_level(new_level=logging.ERROR):
    """
    Temporarily increase logging level to ERROR to suppress warnings.
    Otherwise "Could not parse" warnings are raised every time a getAttribute() query does not find a specific entry in the json file (e.g., query for hmriNIFTI parameter in a jsonNIFTI).
    """
    logger = logging.getLogger()
    original_level = logger.getEffectiveLevel()
    logger.setLevel(new_level)
    try:
        yield # makes the function a generator, allowing the code within the 'with' block to execute
    finally:
        logger.setLevel(original_level)