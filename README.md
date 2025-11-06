# Bidsification of the IronSleep MRI data

This repository contains the code to bidsifiy a set of MRI data. First, the DICOM-to-NIfTI conversion can be performed optionally using the scripts provided in this repository. Thereafter, the DICOM-imported NIfTI data is bidsified using [Bidsme](https://github.com/CyclotronResearchCentre/bidsme). You can find descriptions of the functionalities and how to run the processing in the documentation below. Further information is provided in the [docs/ directory](docs/) of this repository and on the [MPI CBS Wiki on Confluence](https://wiki.cbs.mpg.de/spaces/~kuegler/pages/214368257/IronSleep+data+analysis). If you are having trouble accessing the pages, please [reach out to me](mailto:kuegler@cbs.mpg.de?subject=Permissions%20missing%20MPM_bidsification). 

>The two steps are part of a larger data processing pipeline, designed to automatically analyze the MRI data acquired in the [IronSleep](https://www.cbs.mpg.de/neurophysics/third-party-funding/ironsleep) project. The whole documentation is available on Confluence (see the link above).


## DICOM-to-NIfTI conversion

For the full documentation of this step, please refer to the [DICOM-to-NIfTI documentation](docs/doc_DICOM-to-NIfTI.md). a brief summary of the key points is provided in this section.


