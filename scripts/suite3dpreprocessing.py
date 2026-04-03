# %%
## import stuff
from datetime import date
from matplotlib import pyplot as plt
import numpy as np
import os
import tifffile as tiff
import glob as glob

from pathlib import Path

# we need to set the current path to the directory
# containing the suite3d repository, this hack should
# do the trick
os.chdir(os.path.dirname(os.path.abspath("")))

from suite3d.job import Job
from suite3d import io
from suite3d import plot_utils as plot
# %%
# define path to data
#path = Path("/mnt/imaging1/imaging1/Veronique/2p_datasets/OFL/477116/20251118") # this is actually path to multiday data not 3d data
path = Path("/data/ofl_2p/20251118/split_tifs/")
job_root_dir = r'/data/ofl_2p/20251118'
job_id = 'xy_1000'
results_root_dir = Path(r'/data/ofl_2p/20251118/results')
# Check if it exists
if path.exists():
    print("Path exists!")
else:
    print("Path does not exist.")

results_path =  results_root_dir / job_id
# get tif files
tifs = io.get_tif_paths(path)
for tif in tifs: print(tif)



# %%
print(io.get_vol_rate(tifs[0]))
# %%
# Set the mandatory parameters
# for now some parameters are just guesses
params = {
    # volume rate
    'fs': io.get_vol_rate(tifs[0]),

    # planes to analyze (we have 3 planes)
    'planes' : np.array([0,1,2]),
    # number of planes recorded
    'n_ch_tif' : 3,

    # Decay time of the Ca indicator in seconds. 1.3 for GCaMP6s. This example is for GCamP8m
    'tau' : 1.3,
    'lbm' : False,
    'num_colors' : 1, # how many color channels were recorded by scanimage
    'functional_color_channel' : 0, # which color channel is the functional one
     # voxel size in z,y,x in microns
    'voxel_size_um' : (30, 0.84, 0.84),
    # number of files to use for the initial pass
    # usually, ~500 frames is a good rule of thumb
    # we will just use 200 here for speed
    'n_init_files' :  1,  # more of those makes it crash due to mem issues
    "init_n_frames": 500,

    # 3D GPU registration - fast!
    '3d_reg' : True,
    'gpu_reg' : True,

    # note : 3D CPU is not supported yet
    'subtract_crosstalk' : False, # turn off some lbm-only features
    'fuse_strips' : False, # turn off some lbm-only features
    "cell_filt_xy_um": 8,


    "split_tif_size": 100,
    "peak_thresh": 0.5,
    "extend_thresh": 0.005,
    #"activity_thresh": 8.0,
    #"percentile": 90.0,
    #"extend_thresh": 0.1,
    #"max_pix": 1000,




}



# %%
### Create the job
job = Job(job_root_dir,job_id, tifs = tifs,
          params=params, create=True, overwrite=True, verbosity = 3)
job.params.update(params)

# %%
job.run_init_pass()
# %%
# If you have large tiffs, split the large tiffs into files of size 100 after registration
job.params['split_tif_size'] = 100
# %%
# OPTIONAL: load and take a look at the reference image
summary = job.load_summary()
ref_img = summary['ref_img_3d']

# # view 1 plane at a time
plot.show_img(ref_img[0], figsize=(3,4))
plot.show_img(ref_img[1], figsize=(3,4))
plot.show_img(ref_img[2], figsize=(3,4))

# # interactive 3D viewer
# plot.VolumeViewer(ref_img)
# %%
job.register()
# %%
corr_map = job.calculate_corr_map()
# %%
res = job.load_corr_map_results()
vmap = res['vmap']
# %%
plot.show_img(ref_img[0], figsize=(3,4))
plot.show_img(res['max_img'][0], figsize=(3,4))

plot.show_img(ref_img[1], figsize=(3,4))
plot.show_img(res['max_img'][1], figsize=(3,4))

plot.show_img(ref_img[2], figsize=(3,4))
plot.show_img(res['mean_img'][2], figsize=(3,4))
# %%
job.params['patch_size_xy'] = (1000, 1000)
# for speed, only segment a single patch
job.segment_rois()


# %%
job.compute_npil_masks()
traces = job.extract_and_deconvolve()
# %%
job.export_results(results_path,result_dir_name='rois')
# %%
print(np.__version__)
# %%

# %%

# %% [sql]
# 
# %%
