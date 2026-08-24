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
    """Infer the target MPM modality of a sensitivity-map sequence.

    The function scans neighboring sequence names and returns the first
    matching contrast label used for sensitivity-map linkage logic.
    Search is case-insensitive and entries containing "smap" are skipped.

    Args:
        seq_list (list[str]):
            Ordered list of sequence identifiers (typically one session).
        current_index (int):
            Index of the current sensitivity-map sequence in ``seq_list``.
        search_direction (str, optional):
            Direction of search from ``current_index``.

            Options:
                - "forward": scan entries after the current index.
                - "backward": scan entries before the current index.

            Default: "forward".

    Returns:
        str | None:
            "T1w", "PDw", or "MTw" when a matching sequence is found;
            otherwise ``None``.

    Raises:
        ValueError:
            If ``search_direction`` is neither "forward" nor "backward".

    Example:
        >>> modality = find_smap_modality(seq_list, seq_index, "backward")
        >>> if modality is None:
        ...     print("No target modality found")
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
    """Convert flexible plugin-option values to a boolean.

    This helper normalizes values typically passed through CLI/plugin options.

    Args:
        argument (str | int | bool):
            Input value to normalize.

            Accepted values:
                - ``True`` / ``False`` (bool)
                - "true" / "false" (case-insensitive str)
                - ``1`` / ``0`` (int)
                - "1" / "0" (str)

    Returns:
        bool | int:
            - ``True`` or ``False`` for valid inputs.
            - ``-1`` for invalid/unrecognized values.

    Example:
        >>> bidsmap_step = argument_to_bool("false")
        >>> if bidsmap_step == -1:
        ...     raise ValueError("Invalid value for bidsmap_step")
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
    """Temporarily override the root logger level inside a ``with`` block.

    Useful when probing optional metadata keys where warnings are expected.
    After the context exits, the original logging level is restored.

    Args:
        new_level (int, optional):
            Temporary logging level to apply for the duration of the context.
            Default: ``logging.ERROR``.

    Yields:
        None:
            Control is yielded to the wrapped code block.

    Example:
        >>> with temporary_logging_level(logging.ERROR):
        ...     value = recording.getAttribute("ConversionSoftware")
    """
    logger = logging.getLogger()
    original_level = logger.getEffectiveLevel()
    logger.setLevel(new_level)
    try:
        yield # makes the function a generator, allowing the code within the 'with' block to execute
    finally:
        logger.setLevel(original_level)