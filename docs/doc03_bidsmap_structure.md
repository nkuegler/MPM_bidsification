# Bidsmap structure

This note documents the structure used in bidsmaps such as
`supplementary/bidsmaps/example_bidsmap_MPM_HISTOPARKcombined.yaml`.

## 1) Top-level structure

A bidsmap is a YAML tree with:

- `__bids__`: target BIDS version (for example `1.11.0`)
- modality block (here: `MRI`)
- source-category blocks inside the modality

In this file, MRI contains two source categories:

- `hmriNIFTI`: data converted with SPM DICOM import
- `jsonNIFTI`: data converted with dcm2niix

Both categories follow the same mapping schema.

## 2) Category and section layout

Each source category is organized into sections such as:

- `__ignore__`: patterns that should be skipped
- `anat`, `fmap`, `dwi` (and potentially other BIDS modality folders)

Each mapping entry in a section contains the same core fields:

- `provenance`: example source file used when creating the map (may be `~`)
- `example`: expected BIDS-like output filename template. For the actual definition of the BIDS output filename, see the `bids` field below.
- `checked`: whether Bidsme should try to verify the entry when running the `bidsme.mapper` command 
- `model`: BIDSme modality model (for example `anat:MPM`, `fmap:TB1AFI`)
- `suffix`: BIDS suffix (`MPM`, `MEGRE`, `TB1AFI`, `dwi`, ...)
- `attributes`: matching criteria in source metadata (for example `ProtocolName`, `SeriesDescription`). All files that match **all** attributes are converted according to this entry during the bidsification step. Each sequence must be uniquely recognized by its attributes. If there are ambiguous matches, Bidsme will raise an error.
- `bids`: entity definitions used for output naming (`acq`, `run`, `echo`, `part`, ...). **This is what actually defines the BIDS output filename.** 
- `json`: sidecar JSON fields to write into the BIDS output JSON

## 3) hmriNIFTI vs jsonNIFTI in practice

- `hmriNIFTI` entries often use Siemens CSA paths in `json` fields, for example:
  - `<CSASeriesHeaderInfo/MrPhoenixProtocol/...>`
  - `<CSAImageHeaderInfo/RealDwellTime>`
- `jsonNIFTI` entries usually read flatter keys provided by dcm2niix (already in BIDS-conform format), for example:
  - `<EchoTime>`, `<ReceiveCoilName>`, `<PartialFourier>`, `<TotalReadoutTime>`

So the structure is the same, but the available metadata keys differ depending on DICOM-to-NIfTI conversion method.

## 4) How values are defined in `bids` and `json`

Values can come from three places.

### A) Direct metadata lookup from temporary JSON files

Use angle brackets:

- `<EchoTime>`
- `<ProtocolName>`
- `<CSASeriesHeaderInfo/MrPhoenixProtocol/sPat/lAccelFactPE>`

This reads fields from the prepared temporary sidecar JSON for the current recording.

### B) Metadata lookup with formatting/transforms

Use prefixed transforms in the same angle-bracket expression:

- `<format02d:EchoNumbers>`
- `<format03d:AcquisitionNumber>`
- `<round10:scale-3:EchoTime>`
- `<scale-9:CSAImageHeaderInfo/RealDwellTime>`

Common usage:

- `formatXXd` for zero-padded integers in filename entities (python-like notation)
- `scale-N` for unit scaling (scaleN for positive, scale-N for negative powers of ten)
- `roundN` for controlled numeric rounding

### C) Custom variables provided by the plugin

Use double-angle custom placeholders:

- `<<custom:T1w_run_counter>>`
- `<<custom:part>>`
- `<<custom:NonlinearGradientCorrection>>`
- `<<custom:PartialFourier>>`
- `<<custom:ParallelAcquisitionTechnique>>`
- `<<custom:RepetitionTime>>`
- `<<custom:tr_index>>`

These values are populated in the active plugin through `recording.custom[...]`.
For this combined map, examples are implemented in:

- `plugins_bidsme/combined_dcm2niix_dcmImport/plugin_bidsify_combined_dcm2niix_DcmImport_nk.py`

This is how one map can support both SPM-imported and dcm2niix-converted data:
plugin logic detects available metadata and derives harmonized custom fields.

## 5) Defining matching logic (`attributes`)

`attributes` defines how an input series is recognized. Typical patterns are:

- one exact value:
  - `ProtocolName: t2_spc_da-fl_sag_p2_iso`
- a list of accepted variants:
  - `ProtocolName: ['t1w_kp_mtflash3d_v1s_0p6', 't1w_kp_mtflash3d_v1s_caipi', ...]`

During mapping/bidsification, BIDSme uses these fields to select the entry,
then fills `bids` filename entities and `json` sidecar keys using the rules above.

> Most of the either `ProtocolName` or `SeriesDescription` are sufficient to uniquely identify a sequence. If both are specified, the sequence must match **both** attributes. 
    > `ProtocolName` often serves as a parent category, while `SeriesDescription` adds some granularity. For example, `ProtocolName` may be `t1w_kp_mtflash3d_v1s_0p6` and `SeriesDescription` may be `t1w_kp_mtflash3d_v1s_0p6_ND` or `t1w_kp_mtflash3d_v1s_0p6`. This can be used to distinguish between gradient nonlinearity corrected (no ND) and non-corrected versions (ND) of the same sequence.

## 6) Minimal checklist when adding new entries

1. Add/adjust `attributes` so the sequence is uniquely recognized.
2. Set `model` and `suffix` to the intended BIDS datatype.
3. Define `bids` entities (set fixed values, metadata lookups, or custom variables).
4. Define required `json` metadata (direct, transformed, or custom).
5. If metadata differs between SPM and dcm2niix, distinguish by using both hmriNIFTI and jsonNIFTI categories in the Bidsmap. There is also the option to implement custom variables (`recording.custom[...]`) in the plugin and use `<<custom:...>>` in the map.
