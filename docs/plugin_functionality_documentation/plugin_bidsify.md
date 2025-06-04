**\---- under construction ----**



# naming smaps properly
`find_smap_modality` - checks the next files in the directory for the name of the MPM sequences (T1w, MTw, PDw)

Multiple counters and conditional statements are used to define the `run-` entity of the smaps properly to match the `run-` entity of the corresponding images in the `anat` directory. 
The following **assumptions** are made based on my data sets:
- There are either only head/array sensitivity maps (*e.g.*, Terra) or head and body sensitivity maps (*e.g.*, Prisma)
- If the `rec_id` contains "head", it does not contain "array".

> If these assumptions are not met, the counters may not be incremented correctly.