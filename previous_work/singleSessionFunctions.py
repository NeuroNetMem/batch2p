# -*- coding: utf-8 -*-
"""
Created on Fri May  3 15:08:09 2024

@author: veron
"""

# Set working directory
import os
os.chdir('C:\\Users\\veron\\OneDrive\\Documents\\Master\\Year 2\\Internships\\Data_Analyses')
from Opening_functions import *
import numpy as np
import pandas as pd
import scipy.io as spio
import glob as glob
from scipy.ndimage import gaussian_filter1d
from scipy.stats import sem
from pathlib import Path
import matplotlib.pyplot as plt
from collections import defaultdict
import seaborn as sns
# Import your modules
os.chdir('C:\\Users\\veron\\OneDrive\\Documents\\PhD\\Analyses')
from functionsRunningSpeed import *

#%%
# Constants
dt = 1./1000  # Sampling rate in kHz
t_on, t_off = -2000, 5000  # Time window for analysis in milliseconds

def compute_speed(vrDistance):
    """ Compute speed from distance measurements. """
    pos = gaussian_filter1d(vrDistance, sigma=2)
    speed = np.diff(pos) / (dt * 10)
    return gaussian_filter1d(speed, 30)
#%%
def analyze_single_session(digital_in, digital_out, long_var, data):
    """Analyze a single session for an animal given pre-loaded data."""
    # Assuming data has been built already outside this function

    vrDistance = long_var[:, 1].astype(float)
    speed = compute_speed(vrDistance)

    animal_results = defaultdict(lambda: {'avg_speeds': [], 'sems': [], 'trial_count': 0})
    for sound in [1, 2, 3]:
        subset = data.query('env_label == @sound & sound_onset.notna()')
        #if len(subset) < 10:
            #continue

        # Assuming t_on and t_off are defined; include them as parameters if they vary
        speed_mat = computed_sliced_matrix(subset, speed, t_on, t_off)
        avg_speed_per_time_point = np.mean(speed_mat, axis=0)
        sem_per_time_point = sem(speed_mat, axis=0)

        animal_results[sound]['avg_speeds'].append(avg_speed_per_time_point)
        animal_results[sound]['sems'].append(sem_per_time_point)
        animal_results[sound]['trial_count'] = len(subset)

    return animal_results





