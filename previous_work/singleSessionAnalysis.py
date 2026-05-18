# -*- coding: utf-8 -*-
"""
Created on Fri May  3 15:18:19 2024

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
os.chdir('C:\\Users\\veron\\OneDrive\\Documents\\PhD\\Analyses\\soundExperiments')
from functionsRunningSpeed import *
from singleSessionFunctions import *
#%%
file_path_variable = search_for_file_path()
#print ("\nfile_path_variable = ", file_path_variable)
os.chdir(file_path_variable)
cwd = os.getcwd()

mats = []
filename = glob.glob('*_decoded.mat')[0]
matStruct = spio.loadmat(filename)
#%%
os.chdir(r"C:\Users\veron\Desktop\officialSoundData\batch2\456225\20240509")
matStruct = spio.loadmat("20240509-094332_560_decoded.mat")
#%%
#Define digital input and digital output
digital_in = matStruct["digitalIn"].astype(int)
digital_out = matStruct["digitalOut"].astype(int)
long_var = matStruct['longVar']
data = build_trial_matrix(digital_in, digital_out)
#%%
runningSpeedDict = analyze_single_session(digital_in, digital_out, long_var, data)
#%%
#Plot all three separate
plt.figure(figsize=(15,5))
for sound in [1,2,3]:
    avg_speeds = np.array(runningSpeedDict[sound]['avg_speeds'][0])
    sems = np.array(runningSpeedDict[sound]['sems'][0])
    plt.subplot(1,3,sound)
    plt.title(f'sound: {sound}')
    t = np.linspace(t_on/1000, t_off/1000, t_off- t_on) # Return evenly spaced numbers over a specified interval.
    plt.plot(t, avg_speeds)
    #plt.fill_between(t, avg_vel - std_vel, avg_vel + std_vel, alpha = 0.5)
    plt.fill_between(t, avg_speeds - sems, avg_speeds + sems, alpha = 0.5)
    plt.axvline(x = 0, c= 'r',linestyle='--',label='sound on')
    plt.axvline(x = 3, c= 'k',linestyle='--',label='sound off') # Sound onset timepoint from trial_matrix.
    sns.despine()
    plt.xlabel('time from sound onset (s)')
    plt.ylabel('Avg speed (cm/s)')
    plt.ylim([0,40])
    plt.legend()

#%%Plot all three stacked
# Setup for the plot
plt.figure(figsize=(10, 6))
plt.title('Average Running Speed with SEM by Sound Condition')

# Assuming t_on and t_off are predefined
for sound in [1, 2, 3]:
    avg_speeds = np.array(runningSpeedDict[sound]['avg_speeds'][0])
    sems = np.array(runningSpeedDict[sound]['sems'][0])

    # Generating time points from t_on to t_off
    t = np.linspace(t_on / 1000, t_off / 1000, t_off - t_on)

    # Plot each line with label and error shading
    plt.plot(t, avg_speeds, label=f'Environment {sound}')
    plt.fill_between(t, avg_speeds - sems, avg_speeds + sems, alpha=0.2)

# Adding annotations and labels
plt.axvline(x=0, color='r', linestyle='--', label='Sound on', )
plt.axvline(x=3, color='k', linestyle='--', label='Sound off', )  # Assuming sound off at 3 seconds

sns.despine()  # Improve aesthetics by removing top and right spines
plt.xlabel('Time from sound onset (s)')
plt.ylabel('Avg speed (cm/s)')
plt.ylim([0, 40])  # You might want to adjust these limits based on your actual data
plt.legend()

plt.show()
#%%
























