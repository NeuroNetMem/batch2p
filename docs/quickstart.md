# Quickstart instructions


## Running your first session

batch2p is a suite of 3 commands:
- `batch2p` runs a data analysis pipeline for two photon data
- `batch2p-gui` helps with setting up a batch2p session in a graphical user interface, enabling users to easily configure parameters, file locations etc
- `batch2p-multi` helps with setting up multiple sessions from a prototype and a list of data directories

The full documentation for these commands can be foudn in this folder. Here we just give an example of a very simple workflow.

`batch2p` gets all the information it needs to run from a `data.json` file. You can find an example of this file at [data_suite2p.json](data_suite2p.json).

The data.json file contains the location of a parameter file (here an [example](params_default_suite2p.json)), the locations of the data files (tiff, and, optionally, b64), the desired location of the result files and the locations of the temp and scratch directories to be used for making local working copies of the data and for intermediate result files.
 You can run `batch2p` by simpling giving the command
```bash
batch2p data.json
```

To test that the configurations are valid and that all files are present and readable at the specified location you can run
```bash
batch2p --dry-run data.json
```
This is advisable especially when running a number of jobs in series and in parallel, to spot issues that may cause a crash long after a job has started.

You can start with the examples of data and parameter files here and edit them to suit your needs, either in a text editor or using [batch2p_gui](batch2p_gui.md).

It is sometimes needed to run preprocessing on a number of data sessions with the same configuration and parameters. This can be done with [batch2p-multi](batch2p-multi.md).

The basic call syntax for `batch2p-multi` is as follows
```bash
batch2p-multi proto_data.json dirs_list.txt --output-dir batches --params-file params.json
```
`dirs.list.txt` is a text file containing a list of absolute paths to the data directories to be processed.
One can use the unix command `ls -d` to generate these lists. For example
```bash
ls -d "$PWD"/4*/2026101[34] > dirs_list.txt
```
will list all the data directories found in the current directory that start with `4`, and in there those relative to days `20261013` or `20261014`. Note that the prefix `"$PWD"/` is needed to make the paths absolute. For a tutorial on how to write these unix commands see for example [here](https://linuxize.com/post/linux-wildcards-and-globbing/).
The output of `batch2p-multi` will be a directory `batches` containing the data.json files for each session to be processed.
To run these sessions in series, we can use a shell for loop. Probably wise to begin with a dry run:
```bash
cd batches
for bfile in *.json ; do echo $bfile ; batch2p --dry-run $bfile  ; done
```
If the output of this is all OK we are ready to preprocess the data, for example with
```bash
for bfile in *.json ; do echo $bfile ; batch2p $bfile &>> run.log ; done
```
This will run preprocessing for all sessions and save all of the logging information in the run.log file. Note that this is slightly overkill as the same information is also saved in the batch2p output directories

