# -*- coding: utf-8 -*-
"""
Created on Tue Feb 13 10:03:13 2024

@author: veron
"""

#%%
# Import 
import numpy as np
import base64
import struct
from cobs import cobs
from collections import namedtuple
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.pyplot import plot
from tqdm.notebook import tqdm
import scipy.signal
from scipy.io import savemat
import rawpy
import imageio
import os
import pandas as pd

#%%
def invert_polarity(digital_channel):
    '''
    Inverts channel polarity.

    Parameters:
        digital_channel (array-like): Digital channel data.

    Returns:
        array-like: Digital channel data with inverted polarity.
    '''
    digital_channel = np.logical_not(digital_channel).astype(int)
    return digital_channel

#%%
def compute_switch(digital_channel):
    '''
    Compute all transitions in the digital channel.

    Parameters:
        digital_channel (array-like): Digital channel data.

    Returns:
        array-like: Indices of all transitions in the digital channel.
    '''
    digital_channel = digital_channel.astype(int)
    onsets = np.where(np.diff(digital_channel) != 0)[0]
    return onsets

#%%
def clean_switches(switch_list, time_th=500):
    '''
    Clean switch list by removing transitions that are too close.

    Parameters:
        switch_list (array-like): List of indices representing transitions.
        time_th (int, optional): Threshold to remove close transitions, in indexes. Default is 500.

    Returns:
        array-like: Cleaned switch list with transitions further apart than time_th.
    '''
    clean_switch = []
    for i in range(0, len(switch_list), 2):
        if i+1 < len(switch_list):
            if abs(switch_list[i+1]-switch_list[i]) > time_th:
                clean_switch.append(switch_list[i])
                clean_switch.append(switch_list[i+1])
        else:
            clean_switch.append(switch_list[i])
    return np.asarray(clean_switch)

#%%
def compute_onsets(digital_channel):
    '''
    Compute transitions 0->1 in digital channel.

    Parameters:
        digital_channel (array-like): Digital channel data.

    Returns:
        array-like: Indices of transitions from 0 to 1 in the digital channel.
    '''
    digital_channel = digital_channel.astype(int)
    onsets = np.where(np.diff(digital_channel) == 1)[0]+1
    return onsets

#%%
def compute_offsets(digital_channel):
    '''
    Compute transitions 1->0 in digital channel.

    Parameters:
        digital_channel (array-like): Digital channel data.

    Returns:
        array-like: Indices of transitions from 1 to 0 in the digital channel.
    '''
    digital_channel = digital_channel.astype(int)
    onsets = np.where(np.diff(digital_channel) == -1)[0]
    return onsets

#%%
def good_reward_zones(reward_onsets, rz_onsets, rz_offsets):
    '''
    Check if there are reward presentations in the reward zone.

    Parameters:
        reward_onsets (array-like): Onset timestamps of rewards.
        rz_onsets (array-like): Onset timestamps of reward zones.
        rz_offsets (array-like): Offset timestamps of reward zones.

    Returns:
        list: List of indices of reward zones with reward presentations.
    '''
    good_idxs = []
    for i in range(len(rz_offsets)):
        if np.any(np.logical_and((rz_onsets[i] < reward_onsets), (rz_offsets[i] > reward_onsets))):
            good_idxs.append(i)
    return good_idxs

#%%
def is_sound(sound_onsets, t1, t2):
    '''
    Check if sound onsets occur between t1 and t2.

    Parameters:
        sound_onsets (array-like): Onset timestamps of sound events.
        t1 (float): Start time.
        t2 (float): End time.

    Returns:
        bool: True if sound events occur between t1 and t2, False otherwise.
    '''
    return np.any(np.logical_and((t1 < sound_onsets), (t2 > sound_onsets)))


#%%
def build_trial_matrix(digital_in, digital_out):
    '''Builds trial matrix from digital channels.

       Trials are defined with reward zones: each reward zone that has a reward in it is used to definie a trial.
       - env_onset is given by the first envinronment channel switch after previous revard zone.
       - tunnel1_onset is given by last environent channel switch before the reward zone of the current trial.
       - reward_zone_onset is given by onset of reward zone in current trial
       - tunnel2_onset is given by offset of reward zone in current trial
       - tunnel2 offset is given by first env switch after current reward zone offset (equals next env_onset by definition)
       - reward_onset is given by first reward onset after reward zone onset
       - reward offset is given by first reward offset reward onset
       - sound onset is given by first sound onset after previous reward zone onset (if present)
       - sound offset is given by first sound offset after sound onset (if present)

    '''

    trial_matrix = {'env_onset': [], 'tunnel1_onset': [], 'reward_zone_onset': [],
                    'tunnel2_onset': [], 'tunnel2_offset': [], 'trial_duration': [],
                    'env_label': [], 'control_sound_onset': [], 'control_sound_offset': [],
                    'control_sound_presented': [], 'scary_sound_onset': [], 'scary_sound_offset': [],
                    'scary_sound_presented': [], 'reward_onset': [], 'reward_offset': []}

    timestamp_keys = ['env_onset', 'tunnel1_onset', 'reward_zone_onset',
                      'tunnel2_onset', 'tunnel2_offset', 'control_sound_onset', 'control_sound_offset',
                      'control_sound_presented', 'scary_sound_onset', 
                      'scary_sound_offset', 'scary_sound_presented', 'reward_onset', 'reward_offset']

    for jj in range(16):
        if np.sum(digital_in[:, jj] == 1) > np.sum(digital_in[:, jj] == 0):
            digital_in[:, jj] = 1 - digital_in[:, jj]  

#So, in channel mapping, the different channels are assigned to what they are.
    # channel mapping
    channels_in = {'env1': 10, 'env2': 15, 'env3': 12, 'control_sound': 7,
                   'scary_sound': 8, 'tunnel1': 13, 'tunnel2': 14, 'reward_zone': 9}
    channels_out = {'reward': 0} #check with Jeroen whether this needs to be digital output 1. 

    # extract digital signals
    #This line extracts the signal data for the reward zone from a matrix called digital_in.
    # selects all rows (i.e., all time points) for the specific channel mapped to 'reward_zone' 
    #in the channels_in dictionary.
    reward_zone = digital_in[:, channels_in['reward_zone']]

    # the first env onsets is always missing, so the channel polarity has to be inverted
    #invert_polarity() is a function that inverts the binary signal. 
    #This means that all 1s will become 0s, and all 0s will become 1s.
    env1 = invert_polarity(digital_in[:, channels_in['env1']])
    env2 = digital_in[:, channels_in['env2']]
    env3 = digital_in[:, channels_in['env3']]
    control_sound = digital_in[:, channels_in['control_sound']]
    scary_sound = digital_in[:, channels_in['scary_sound']]
    # check id control_sound is witched, if True, switch it back -> duplicate for scary sounds
    if sum(control_sound)/len(control_sound) > 0.5:
        control_sound = invert_polarity(control_sound)
    reward = digital_out[:, channels_out['reward']] #check wheher this also needs to be duplicate for scary sounds? 
    #check if scary sound is switched. 
    if sum(scary_sound)/len(scary_sound) > 0.5:
        scary_sound = invert_polarity(scary_sound)
    reward = digital_out[:, channels_out['reward']] #check wheher this also needs to be duplicate for scary sounds? 
  
    # compute environment onsets and offsets
    # adds first env1 onset at 0
    #np.hstack() is a function in NumPy that horizontally stacks arrays.
    #For env1, it adds an onset at time 0. This is necessary because the comment says that the first env1 onset is 
    #always missing.np.asarray([0.0]) creates an array with a single value [0.0], which is then horizontally stacked 
    #(concatenated) with the computed switches from compute_switch(env1). This ensures that the first onset is at time 0.
    env1_switches = np.hstack([np.asarray([0.0]), compute_switch(env1)])
    env2_switches = compute_switch(env2)
    env3_switches = compute_switch(env3)

    env1_switches = clean_switches(env1_switches)
    env2_switches = clean_switches(env2_switches)
    env3_switches = clean_switches(env3_switches)

    # concatenate environments
    env_switches = np.hstack([env1_switches, env2_switches, env3_switches])

    # build env labels
    env_labels = np.hstack([np.full_like(env1_switches, 1),
                            np.full_like(env2_switches, 2),
                            np.full_like(env3_switches, 3)])

    # sort envrionments onsets, offsets and labels
    sorted_idxs = np.argsort(env_switches)
    env_switches, env_labels = env_switches[sorted_idxs], env_labels[sorted_idxs]

    # reward zone
    rz_onsets = compute_onsets(reward_zone)
    rz_offsets = compute_offsets(reward_zone)

    # reward presentation
    reward_onsets = compute_onsets(reward)
    reward_offsets = compute_offsets(reward)

    good_rz = good_reward_zones(reward_onsets, rz_onsets, rz_offsets)

    rz_onsets = rz_onsets[good_rz]
    rz_offsets = rz_offsets[good_rz]

     # sound presentation
    control_sound_onsets = compute_onsets(control_sound)
    control_sound_offsets = compute_offsets(control_sound)
    scary_sound_onsets = compute_onsets(scary_sound)
    scary_sound_offsets = compute_offsets(scary_sound)
    #FROM HERE TRYING TO FIX THE PROBLEM!!!!!!!!!!!!!!!!!!!!!!!!
    # Check if the lengths of control_sound_onsets and control_sound_offsets are the same
    if len(control_sound_onsets) == len(control_sound_offsets):
        print("Onsets and offsets arrays have the same length. No action needed.")
    else:
        print(f"Onsets and offsets arrays are different lengths: Onsets = {len(control_sound_onsets)}, Offsets = {len(control_sound_offsets)}")
        # We can then proceed to fix the mismatch

    # Define the expected time difference between onset and offset
    expected_difference = 3100  # 3 seconds with tolerance for small variations
    
    # Step 1: Identify the problematic row where the issue occurs
    for i in range(min(len(control_sound_onsets), len(control_sound_offsets))):
        onset = control_sound_onsets[i]
        offset = control_sound_offsets[i]
        
        # Calculate the difference between onset and offset
        time_difference = offset - onset
        
        if time_difference > expected_difference:
            print(f"Problem found at row {i}: Onset = {onset}, Offset = {offset}, Difference = {time_difference}")
            
            # Step 2: Calculate the correct offset
            corrected_offset = onset + 3000  # 3 seconds (3000 ms)
            print(f"Corrected offset for row {i} = {corrected_offset}")
            
            # Insert the corrected offset
            control_sound_offsets = np.insert(control_sound_offsets, i, corrected_offset)
            
            # No need to delete the last value now, so we move to step 3
    
            # Step 3: Automatically swap subsequent rows that are misaligned
            # We will swap rows starting from the one after the corrected row (i+1) until the end of the array
            # or until the time differences between onsets and offsets become valid again.
            
            # Define the range to swap: let's assume the swap continues until we hit a correctly aligned row
            for j in range(i+1, min(len(control_sound_onsets), len(control_sound_offsets))):
                if control_sound_offsets[j] < control_sound_onsets[j]:  # If they are inverted
                    print(f"Swapping row {j}: Onset = {control_sound_onsets[j]}, Offset = {control_sound_offsets[j]}")
                    # Swap the onsets and offsets for this row
                    control_sound_onsets[j], control_sound_offsets[j] = control_sound_offsets[j], control_sound_onsets[j]
                else:
                    # Stop swapping once things are aligned again
                    print(f"Alignment restored at row {j}, stopping swap.")
                    break
            
            break  # Stop after handling the first problem found
    else:
        print("No problems found: all onsets and offsets are within the expected time difference.")
    
                
        


    if len(scary_sound_onsets) == len(scary_sound_offsets):
        print("Onsets and offsets arrays have the same length. No action needed.")
    else:
        print(f"Onsets and offsets arrays are different lengths: Onsets = {len(scary_sound_onsets)}, Offsets = {len(scary_sound_offsets)}")
        # We can then proceed to fix the mismatch

    # Define the expected time difference between onset and offset
    expected_difference = 3100  # 3 seconds with tolerance for small variations
    
    # Step 1: Identify the problematic row where the issue occurs for scary sound
    for i in range(min(len(scary_sound_onsets), len(scary_sound_offsets))):
        onset = scary_sound_onsets[i]
        offset = scary_sound_offsets[i]
        
        # Calculate the difference between onset and offset
        time_difference = offset - onset
        
        if time_difference > expected_difference:
            print(f"Problem found at row {i} for scary sound: Onset = {onset}, Offset = {offset}, Difference = {time_difference}")
            
            # Step 2: Calculate the correct offset
            corrected_offset = onset + 3000  # 3 seconds (3000 ms)
            print(f"Corrected offset for row {i} = {corrected_offset}")
            
            # Insert the corrected offset
            scary_sound_offsets = np.insert(scary_sound_offsets, i, corrected_offset)
            
            # Step 3: Automatically swap subsequent rows that are misaligned
            for j in range(i+1, min(len(scary_sound_onsets), len(scary_sound_offsets))):
                if scary_sound_offsets[j] < scary_sound_onsets[j]:  # If they are inverted
                    print(f"Swapping row {j} for scary sound: Onset = {scary_sound_onsets[j]}, Offset = {scary_sound_offsets[j]}")
                    # Swap the onsets and offsets for this row
                    scary_sound_onsets[j], scary_sound_offsets[j] = scary_sound_offsets[j], scary_sound_onsets[j]
                else:
                    # Stop swapping once things are aligned again
                    print(f"Alignment restored at row {j} for scary sound, stopping swap.")
                    break
            
            break  # Stop after handling the first problem found
    else:
        print("No problems found: all scary sound onsets and offsets are within the expected time difference.")
    

    # reward presentation
    reward_onsets = compute_onsets(reward)
    reward_offsets = compute_offsets(reward)

    # first_trial
    trial_matrix['env_onset'].append(env_switches[0])
    trial_matrix['tunnel1_onset'].append(
        int(np.max(env_switches[env_switches < rz_onsets[0]])))
    trial_matrix['reward_zone_onset'].append(rz_onsets[0])
    trial_matrix['tunnel2_onset'].append(rz_offsets[0])
    trial_matrix['tunnel2_offset'].append(
        int(np.min(env_switches[env_switches > rz_offsets[0]])))

    trial_matrix['trial_duration'].append(np.nan)
    trial_matrix['env_label'].append(int(env_labels[0]))

    #Control sounds
    if is_sound(control_sound_onsets, env_switches[0], rz_onsets[0]):
        control_sound_onset = int(np.min(control_sound_onsets[control_sound_onsets > env_switches[0]]))
        control_sound_offset = int(np.min(control_sound_offsets[control_sound_offsets > control_sound_onset]))
        trial_matrix['control_sound_onset'].append(control_sound_onset)
        trial_matrix['control_sound_offset'].append(control_sound_offset)
        trial_matrix['control_sound_presented'].append(True)
    else:
        trial_matrix['control_sound_onset'].append(np.nan)
        trial_matrix['control_sound_offset'].append(np.nan)
        trial_matrix['control_sound_presented'].append(False)
   
    #Scary sounds
    if is_sound(scary_sound_onsets, env_switches[0], rz_onsets[0]):
        scary_sound_onset = int(np.min(scary_sound_onsets[scary_sound_onsets > env_switches[0]]))
        scary_sound_offset = int(np.min(scary_sound_offsets[scary_sound_offsets > scary_sound_onset]))
        trial_matrix['scary_sound_onset'].append(scary_sound_onset)
        trial_matrix['scary_sound_offset'].append(scary_sound_offset)
        trial_matrix['scary_sound_presented'].append(True)
    else:
        trial_matrix['scary_sound_onset'].append(np.nan)
        trial_matrix['scary_sound_offset'].append(np.nan)
        trial_matrix['scary_sound_presented'].append(False)

    reward_onset = int(np.min(reward_onsets[reward_onsets > rz_onsets[0]]))
    reward_offset = int(np.min(reward_offsets[reward_offsets > reward_onset]))
    trial_matrix['reward_onset'].append(reward_onset)
    trial_matrix['reward_offset'].append(reward_offset)

    if np.max(reward_offsets) < np.max(reward_onsets): 
        result_float = float(len(digital_in))
        last_sample = np.int64(result_float)
        reward_offsets = np.append(reward_offsets, last_sample)


    # loops reward zones, used for trial definition
    for i in range(1, len(rz_offsets)):
        trial_matrix['env_onset'].append(
            int(np.min(env_switches[env_switches > rz_offsets[i-1]])))
        trial_matrix['tunnel1_onset'].append(
            int(np.max(env_switches[env_switches < rz_onsets[i]])))
        trial_matrix['reward_zone_onset'].append(rz_onsets[i])
        trial_matrix['tunnel2_onset'].append(rz_offsets[i])

        # if the experiment does not end
        if len(env_switches[env_switches > rz_offsets[i]]) > 0:
            trial_matrix['tunnel2_offset'].append(
                int(np.min(env_switches[env_switches > rz_offsets[i]])))
        else:
            trial_matrix['tunnel2_offset'].append(np.nan)

        trial_matrix['trial_duration'].append(np.nan)
        trial_matrix['env_label'].append(
            int(env_labels[np.where(env_switches < rz_offsets[i])[0][-1]]))
        # trial_matrix['env_label'].append(int(env_labels[np.argmax(env_switches[env_switches<rz_onsets[i]])]))
        
        #Control sound
        if is_sound(control_sound_onsets, rz_offsets[i-1], rz_onsets[i]):
            control_sound_onset = int(
                np.min(control_sound_onsets[control_sound_onsets > rz_offsets[i-1]]))
            control_sound_offset = int(
                np.min(control_sound_offsets[control_sound_offsets > control_sound_onset]))
            trial_matrix['control_sound_onset'].append(control_sound_onset)
            trial_matrix['control_sound_offset'].append(control_sound_offset)
            trial_matrix['control_sound_presented'].append(True)
        else:
            trial_matrix['control_sound_onset'].append(np.nan)
            trial_matrix['control_sound_offset'].append(np.nan)
            trial_matrix['control_sound_presented'].append(False)
          
        #Scary sound
        if is_sound(scary_sound_onsets, rz_offsets[i-1], rz_onsets[i]):
            scary_sound_onset = int(
                np.min(scary_sound_onsets[scary_sound_onsets > rz_offsets[i-1]]))
            scary_sound_offset = int(
                np.min(scary_sound_offsets[scary_sound_offsets > scary_sound_onset]))
            trial_matrix['scary_sound_onset'].append(scary_sound_onset)
            trial_matrix['scary_sound_offset'].append(scary_sound_offset)
            trial_matrix['scary_sound_presented'].append(True)
        else:
            trial_matrix['scary_sound_onset'].append(np.nan)
            trial_matrix['scary_sound_offset'].append(np.nan)
            trial_matrix['scary_sound_presented'].append(False)

        reward_onset = int(np.min(reward_onsets[reward_onsets > rz_onsets[i]]))
        reward_offset = int(
            np.min(reward_offsets[reward_offsets > reward_onset]))
        trial_matrix['reward_onset'].append(reward_onset)
        trial_matrix['reward_offset'].append(reward_offset)

    trial_matrix = pd.DataFrame.from_dict(trial_matrix)
    #now concatenate scary- and control environments 
    trial_matrix['sound_onset'] = trial_matrix['control_sound_onset'].combine_first(trial_matrix['scary_sound_onset'])
    trial_matrix['sound_offset'] = trial_matrix['control_sound_offset'].combine_first(trial_matrix['scary_sound_offset'])

    return trial_matrix
#%%
def computed_sliced_matrix(trial_matrix, vel, t_on, t_off):
    """
    Computes a 2D array (trial x timepoints) of velocity values for a given time window around a sound onset.
    for each trial in a trial_matrix dataframe.

    PARAMETERS:
    trial_matrix (pandas.DataFrame): a dataframe containing the trial data.
    vel (numpy.ndarray): a 1D array of velocity values.
    t_on (int): the number of milliseconds before the sound onset to include in the velocity timecourse.
    t_off (int): the number of milliseconds after the sound onset to include in the velocity timecourse.

    RETURNS:
    vel_matrix (numpy.ndarray): a 2D array of velocity values for each trial, with shape (number of trials, t_on + t_off).
    """

    # Initialize the velocity matrix and count variable.
    vel_matrix = np.zeros((len(trial_matrix), t_off-t_on))
    count = 0

    # Cycle over the trials using integer indexing.
    for i in range(len(trial_matrix)):
        # Get the current trial row.
        row = trial_matrix.iloc[i]

        # Check if the row contains valid data.
        if not np.isnan(row["sound_onset"]):
            onset = row["sound_onset"].astype(int) + t_on  # 2 seconds before.
            offset = row["sound_onset"].astype(int) + t_off  # 2 seconds after.
            trial_vel = vel[onset:offset]

            # Add the trial's velocity timecourse to the velocity matrix.
            vel_matrix[count, :] = trial_vel
            count += 1

    # Truncate the velocity matrix to remove rows with NaN values.
    vel_matrix = vel_matrix[:count, :]

    return vel_matrix







