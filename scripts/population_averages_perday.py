#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 20 15:53:47 2024

@author: nnmadmin
"""

# avg rate per session
import glob
import numpy as np
import scipy.io
import pickle
import pandas as pd
import pynapple as nap
import matplotlib.pyplot as plt

n_path = ('/media/nnmadmin/Expansion/Ceph_rotinda_backup_287GB/456225_Freddy')
b_path = ('/media/nnmadmin/Expansion/Ceph_rotinda_backup_287GB/456225_Freddy/decoded_logs')

sessions = [
    # #condition1
    # '20240501' , '20240502', '20240503', '20240506', '20240507',
    # #probe
    # '20240508']
    # #condition2
      '20240513', '20240514', '20240515', '20240517', '20240521', '20240522',
    # #probe
      '20240523'
            ]


psth_scary1_allsessions = []
psth_scary2_allsessions = []
psth_control_allsessions = []
psth_nosound_allsessions = []
psth_scary1_allsessions_std = []
psth_scary2_allsessions_std = []
psth_control_allsessions_std = []
psth_nosound_allsessions_std = []

for s in sessions:
        b_session_path =  (f'{b_path}/{s}')
        n_session_path =  (f'{n_path}/{s}/')

        try: 
            n_file = glob.glob(str(n_session_path)+'neural_data.pickle')[0]
            l_file = glob.glob(str(b_session_path)+'_decoded_log.mat')[0]
            t_file = glob.glob(str(b_session_path)+'_trial_data.csv')[0]

            print(f'processing: \n{l_file} \n{n_file} \n{t_file}')
            
        except IndexError:
            print(f'one or both of the files are mising: \n{n_session_path}')
            continue

        try:
            
            with open(n_file,'rb') as file:
                n_data = pickle.load(file)
                
            l_data = scipy.io.loadmat(l_file)
            
            t_data = pd.read_csv(t_file)
            
            # fix time axis

            digital_in = l_data['digitalIn'].astype(int)
            digital_scan_signal = digital_in[:, 6]
            log_times = l_data['startTS'][0].astype(int)

            onsets = np.where(np.diff(digital_scan_signal) == 1)[0]+1

            real_onset_idx = np.where(np.diff(onsets) <=40)[0][0]  # heuristic <40, should be around 33 actually
            # but now we find the onset when the scanner starts automatically
            onset = onsets[real_onset_idx]

            onset_ts = log_times[onset]
            sync_times_onset = log_times[0] - onset_ts
            sync_times = np.linspace(sync_times_onset, sync_times_onset + ((len(log_times)-1)*1000), len(log_times))
            time_axis = sync_times/pow(10,6) # make it in s
            
            #put spikes in dict 4 pynapple
            
            spike_indeces_2p = n_data['deconvolved']  # get the spike indeces (relative to 2p time axis)
            time_axis_2p = n_data['frame_ts']
            
            the_dict = {}
            for i in range(len(spike_indeces_2p)):  
                key = str(i)
                this_cell_indeces = spike_indeces_2p[i]  # get spike indeces of this cell
                this_cell_times = np.array(time_axis_2p[this_cell_indeces])  # get spike times of this cell
                the_dict.update({key : this_cell_times})
                
            ts = nap.TsGroup(the_dict)
            
            # get sound events
            # find scary1 & 2 events
            scary1_trls = np.argwhere(t_data['env_label']==2)
            scary2_trls = np.argwhere(t_data['env_label']==3)
            
            # get sound onsets of scary 1 & 2
            scary_onsets = t_data['scary_sound_onset'].values  # take the onset values from the table
            scary1_onsets = scary_onsets[scary1_trls]
            scary2_onsets = scary_onsets[scary2_trls]   
            
            scary1_onsets = scary1_onsets[scary1_onsets>=0]  # remove nans etc
            scary1_onsets = scary1_onsets.astype(int)  # make int since these are indeces
            
            scary2_onsets = scary2_onsets[scary2_onsets>=0]  # remove nans etc
            scary2_onsets = scary2_onsets.astype(int)  # make int since these are indeces
            
            scary1_onset_times = time_axis[scary1_onsets]
            scary2_onset_times = time_axis[scary2_onsets]
            
            ts_scary1 = nap.Ts(scary1_onset_times)
            ts_scary2 = nap.Ts(scary2_onset_times)

            control_onsets = t_data['control_sound_onset'].values  # take the onset values from the table
            control_onsets = control_onsets[control_onsets>=0]  # remove nans etc
            control_onsets = control_onsets.astype(int)  # make int since these are indeces
            control_onset_times = time_axis[control_onsets]
            ts_control = nap.Ts(control_onset_times)
            
            ## get events of 'no sound' trials
            
            # get the VR distance (should be fixed between environment onset & sound onset, around 500mm)
            long_var = l_data['longVar']
            vrDistance = long_var[:, 1].astype(float)
            
            # find no sound trials
            no_sound_trls = np.argwhere(np.isnan(t_data['control_sound_onset']) & np.isnan(t_data['scary_sound_onset']))
            # get env onsets of no sound trials
            env_onsets = t_data['env_onset'].values
            env_onsets = env_onsets.astype(int)
            no_env_onsets = env_onsets[no_sound_trls]
            
            # take the no sound trials and add 500 to the VR to get the no sound onset
            # no_sound_vr_onsets = vrDistance[no_env_onsets]+500
            # no_sound_vr_onsets = no_sound_vr_onsets.astype(int)
            
            # no_sound_vr_idx = np.zeros((len(no_sound_vr_onsets),1))
            # for i in range(len(no_sound_vr_onsets)):
            #     tmpidx = np.argwhere(vrDistance==no_sound_vr_onsets[i])
            #     no_sound_vr_idx[i]=max(tmpidx)
                
            # no_sound_vr_idx = no_sound_vr_idx.astype(int)

            # no_sound_times = time_axis[no_sound_vr_idx] # these are the times to lock to
            # no_sound_times = no_sound_times.ravel()
            
            # ts_nosound = nap.Ts(no_sound_times)
        
            # do psth for scary, control, and nosound
            psth_scary1 = nap.compute_perievent(ts, ts_scary1, (-5, 8))
            psth_scary2 = nap.compute_perievent(ts, ts_scary2, (-5, 8))
            psth_control = nap.compute_perievent(ts, ts_control, (-5, 8))
 #           psth_nosound = nap.compute_perievent(ts, ts_nosound, (0, 3))
            
            # normalise psth by number of trials and overall cell rate
            
            psth_scary1_all= []
            psth_scary2_all= []
            psth_control_all=[]
            psth_nosound_all = []
            for i in range(len(ts)):
                psth_this_scary1 = np.sum(psth_scary1[i].count(0.3), 1) / (len(scary1_onsets) * ts.rate[i])
                psth_this_scary2 = np.sum(psth_scary2[i].count(0.3), 1) / (len(scary2_onsets) * ts.rate[i])
                psth_this_control = np.sum(psth_control[i].count(0.3), 1) / (len(control_onsets) * ts.rate[i])
#                psth_this_nosound = np.sum(psth_nosound[i].count(0.3), 1) / (len(no_sound_vr_onsets) * ts.rate[i])
            
                psth_scary1_all.append(psth_this_scary1)
                psth_scary2_all.append(psth_this_scary2)
                psth_control_all.append(psth_this_control)
#                psth_nosound_all.append(psth_this_nosound)
                
            psth_scary1_allsessions.append(np.mean(psth_scary1_all, axis=0))
            psth_scary2_allsessions.append(np.mean(psth_scary2_all, axis=0))
            psth_control_allsessions.append(np.mean(psth_control_all, axis=0))
 #           psth_nosound_allsessions.append(np.mean(psth_nosound_all, axis=0))
            
            psth_scary1_allsessions_std.append(np.std(psth_scary1_all, axis=0))
            psth_scary2_allsessions_std.append(np.std(psth_scary2_all, axis=0))
            psth_control_allsessions_std.append(np.std(psth_control_all, axis=0))
#            psth_nosound_allsessions_std.append(np.std(psth_nosound_all, axis=0))

            
        except:
            print(f'error with: \n{n_session_path}')
            continue
#%% get mean values

env2_all= np.mean(psth_scary1_allsessions, axis = 1)
env3_all = np.mean(psth_scary2_allsessions, axis = 1)
env1_all = np.mean(psth_control_allsessions, axis = 1)

env2_all_err = np.std(psth_scary1_allsessions, axis = 1)/np.sqrt(len(psth_scary1_allsessions))
env3_all_err = np.std(psth_scary2_allsessions, axis = 1)/np.sqrt(len(psth_scary2_allsessions))
env1_all_err = np.std(psth_control_allsessions, axis = 1)/np.sqrt(len(psth_control_allsessions))

#%% plot

plt.figure(figsize=(10, 5))

plt.errorbar(np.array([1,2,3,4,5,6]), env1_all, yerr = [np.asarray(env1_all_err), np.asarray(env1_all_err)], linewidth=3)

plt.errorbar(np.array([1.1,2.1,3.1,4.1,5.1,6.1]), env2_all, yerr = [np.asarray(env2_all_err), np.asarray(env2_all_err)], linewidth=3)

plt.errorbar(np.array([1.2,2.2,3.2,4.2,5.2,6.2]), env3_all, yerr = [np.asarray(env3_all_err), np.asarray(env3_all_err)], linewidth=3)


plt.xlabel("days", fontsize=20)
plt.xticks(fontsize=16)
plt.ylabel("normalized firing rate", fontsize=20)
plt.yticks(fontsize=16)
plt.legend(["control", "scary1", "scary2"], fontsize=12)
plt.title("condition 1", fontsize = 20)

plt.savefig('/media/nnmadmin/Expansion/firingrate_condition1.png', format='png', dpi=200)

#%% plot population time course per session

s = 1

x_time = np.arange(-4.85, 7.8, 0.3)

plt.figure(figsize=(10, 5))
plt.plot(x_time, psth_scary2_allsessions[s])
plt.plot(x_time, psth_scary1_allsessions[s])
plt.plot(x_time, psth_control_allsessions[s])



plt.xlim(-5, 8)
plt.ylabel("normalized count")
plt.xlabel("sound onset (s)")
plt.axvline(0.0, color="grey")
plt.axvline(3.0, color="grey")
plt.xlim(-2,5)