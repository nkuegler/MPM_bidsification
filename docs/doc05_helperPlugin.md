# Helper functions for plugin development

Detailed documentation is stored in the Sphinx-style docstrings of
`plugins_bidsme/plugin_helper_functions.py`.

## find_smap_modality(seq_list, current_index, search_direction="forward")

Finds the target MPM modality (`T1w`, `PDw`, `MTw`) for a sensitivity-map
sequence by scanning neighboring sequence names forward or backward.

## argument_to_bool(argument)

Converts plugin option values (bool/string/int) to `True` or `False` and
returns `-1` for invalid values so callers can handle errors explicitly.

## temporary_logging_level(new_level=logging.ERROR)

Context manager that temporarily changes the root logger level (default
`ERROR`) to suppress expected metadata-parsing warnings during probing.

