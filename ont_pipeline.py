#!/usr/bin/env python3
import sys
import os
import argparse
import configparser
import shutil
import pandas as pd
import subprocess as sp
import yaml
# from qc import *
# from mapping import *
# from baseCalling import base_calling

def get_parser():

    parser = argparse.ArgumentParser(description='A Pipeline to process fast5.')
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')

    # required argumnets:
    required.add_argument("-i",
                        "--input",
                        type=str,
                        dest="input",
                        help='input path')
    required.add_argument("-r",
                        "--ref",
                        type=str,
                        dest="reference",
                        help='reference genome')
    required.add_argument("-p",
                        type=str,
                        dest="protocol",
                        help='sequencing protocol. This information is needed for mapping.'
                             'valid options are dna, rna or cdna')
    return parser

def read_flowcell_info(config):
    """
    Check the flowcell path to find the info needed for base calling
    """
    input = config["input"]["name"]
    info_dict = dict()
    base_path = os.path.join(config["paths"]["baseDir"]+input)
    if not os.path.exists(config["paths"]["outputDir"]+input):
        shutil.copytree(base_path,config["paths"]["outputDir"]+input)
    else:
        print("a flowcell with the same ID already exists!!") # todo should be changed to sys.exit
    flowcell_path = os.path.join(config["paths"]["outputDir"]+input)
    info_dict["flowcell_path"] = flowcell_path
    if not os.path.exists(flowcell_path+"/fast5_pass"):
         sys.exit("fast5 path doesnt exist.")
    info_dict["fast5"] = os.path.join(flowcell_path,"fast5_pass")

    summary_file = [filename for filename in os.listdir(flowcell_path) if filename.startswith("final_summary")]
    if summary_file == []:
         sys.exit("final summary file doesnt exist.")
    assert len(summary_file) == 1
    summary_file = os.path.join(flowcell_path,summary_file[0])
    with open(summary_file,"r") as f:
        for line in f.readlines():
            if line.startswith("protocol="):
                info_dict["flowcell"] = line.split(":")[1]
                if info_dict["flowcell"] not in config["flowcell"]["compatible_flowcells"]:
                    sys.exit("flowcell id is not valid!")
                info_dict["kit"] = line.split(":")[2]
                if info_dict["kit"].endswith("\n"):
                    info_dict["kit"] = info_dict["kit"].split("\n")[0]
                if str(info_dict["kit"]) not in config["flowcell"]["compatible_kits"]:
                    sys.exit("kit id is not valid!")
                return info_dict

    return None

def read_samplesheet(config):
    """
        read samplesheet
    """
    sample_sheet = pd.read_csv(config["info_dict"]["flowcell_path"]+"/SampleSheet.csv",
                               sep = ",", skiprows=[0])
    print(sample_sheet)
    sample_sheet = sample_sheet.fillna("no_bc")
    assert(len(sample_sheet["barcode_kits"].unique())==1)
    bc_kit = sample_sheet["barcode_kits"].unique()[0]
    data=dict()
    for index, row in sample_sheet.iterrows():
        assert(row["Sample_ID"] not in data.keys())
        data[row["Sample_ID"]] = dict({"Sample_Name": row["Sample_Name"], "Sample_Project": row["Sample_Project"],
                                       "barcode_kits": row["barcode_kits"],"index_id": row["index_id"], "Sample_ID": row["Sample_ID"]})
    return bc_kit, data



def report_contamination(config, data, protocol):
    if protocol == 'rna':
        mapping_rna_contamination(config, data)



def main():
    # parse arguments
    args = get_parser().parse_args()

    # read config
    config = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'config.yaml')))
    if not os.path.exists(os.path.basename(os.path.realpath(args.input))):
        sys.exit("input does path not exist")
    else:
        config["input"]=dict([("name",os.path.basename(os.path.realpath(args.input)))])

    # read the flowcell info & copy it over from dont_touch_this to rapidus
    info_dict = read_flowcell_info(config)
    config["info_dict"]=info_dict

    # read samplesheet
    bc_kit,data = read_samplesheet(config)
    config["data"] = data
    config["bc_kit"] = bc_kit

    # write the updated config file under the output path
    configFile = os.path.join(config["paths"]["outputDir"], args.input, "pipeline_config.yaml")
    with open(configFile, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    #run snakemake
    output_directory = os.path.join(config["paths"]["outputDir"], args.input)
    snakefile_directory = os.path.join(os.path.realpath(os.path.dirname(__file__)), "ont_pipeline.Snakefile")
    snakemake_cmd = " snakemake  -s "+snakefile_directory+" --jobs 5 -p --verbose \
                     --configfile "+configFile+" \
                     --directory " + output_directory
    sp.check_output(snakemake_cmd, shell = True)

if __name__== "__main__":
    main()
