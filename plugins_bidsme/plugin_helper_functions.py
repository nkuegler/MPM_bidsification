###############################################################################
# 
# This script contains helper functions for the implementation of custom plugins to be used with Bidsme.
# 
# Author: Niklas Kuegler
# Institution: Max Planck Institute for Cognitive and Brain Sciences, Leipzig, Germany



def find_smap_modality(seq_list: list, current_index: int) -> str:
    """
    Determines the modality of an SMAP sequence from a list of sequences.
    Sensitivity maps (SMAP) are acquired right before the intended modality (T1w, PDw, MTw).
    This function examines the elements in `seq_list` starting from the index 
    immediately after `current_index` and checks for specific modality keywords 
    ("t1w", "pdw", "mtw") in a case-insensitive manner. It returns the first 
    matching modality found.
    Args:
        seq_list (list): A list of sequence names.
        current_index (int): The index of the current sequence in the list.
    Returns:
        str: The modality of the sequence ("T1w", "PDw", or "MTw") if found, 
                otherwise None.
    """

    # Look at subsequent elements
    for i in range(current_index + 1, len(seq_list)):
        element = seq_list[i].casefold()  # Case-insensitive comparison
        
        # Check for modalities
        if "t1w" in element:
            return "T1w"
        elif "pdw" in element:
            return "PDw"
        elif "mtw" in element:
            return "MTw"
        
    return None