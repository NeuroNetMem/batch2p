# suite3dbatch -- a batch interface to suite3d

### Example Usage 
`python scripts/suite3dbatch.py docs/params_default.json docs/data.json`

The parameters are loaded from the first JSON file;  planes is converted to np.array.

The second JSON file `data.json` provides infomation on the input files and some other running options 

1) the list of input TIFF files is constructed from the data list in data.json as follows:
- if an item is a TIFF file, add it to the tifs list, in order
- if an item is a directory, add all the tifs files contained in that directory, in lexicographic order

if a root_path field is present in the data.json file, all pathnames should be relative to that root path.

2) TIFF splitting: if tiff_trim_size > 0, calls split_3d_tiff_into_chunks() with block_size and add_offset arguments from data.json into a temp dir; the split files replace the originals in the pipeline, 
and the temp dir is cleaned up in a finally block.
Functionality: The function splits a 3D TIFF stack (shape: [frames, height, width]) into consecutive chunks of chunk_size frames. Output files are named as <input_stem>_frames_<start>_<end>.tif where end is exclusive. 
It preserves per-page TIFF tags and metadata during the splitting process. If the final chunk contains fewer frames than block_size, it is truncated and excluded from the output.

3) job_root_dir and job_id are also defined in data.json. results_root_dir as well, and defaults to job_root_dir/results if it's not present in data.json


Reproducibility: before running, saves params_used.json and data_used.json (with absolute paths to whatever tifs were actually processed) into results_root_dir/job_id/.

