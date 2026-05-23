#!/bin/bash
#SBATCH --partition=neurophys -w cn151 --gres=gpu:1 --mem-per-cpu=64G

eval "$(mamba shell hook --shell bash)"
mamba activate
mamba activate ofl_2p_analysis

batch2p --working-dir /scratch/battaglia/ /home/battaglia/batches/data.json

