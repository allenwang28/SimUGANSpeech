# -*- coding: utf-8 *-* 
"""Script used to download and preprocess LibriSpeech data. 

This module is used for downloading and processing the files 
provided by LibriSpeech

The LibriSpeech folder structure (from LibriSpeech/README.txt):
<corpus root>
    |
    .- README.TXT
    |
    .- READERS.TXT
    |
    .- CHAPTERS.TXT
    |
    .- BOOKS.TXT
    |
    .- train-clean-100/
                   |
                   .- 19/
                       |
                       .- 198/
                       |    |
                       |    .- 19-198.trans.txt
                       |    |    
                       |    .- 19-198-0001.flac
                       |    |
                       |    .- 14-208-0002.flac
                       |    |
                       |    ...
                       |
                       .- 227/
                            | ...
, where 19 is the ID of the reader, and 198 and 227 are the IDs of the chapters
read by this speaker. The *.trans.txt files contain the transcripts for each
of the utterances, derived from the respective chapter and the FLAC files contain
the audio itself.

Notes:
    So far, we have only been working from the dev-clean folder.
    It should work for all LibriSpeech folders, assuming their folder structures
    are consistent.

Todo:
    * Options for specifying which cepstral coefficients
    * Test for other folders
    * Add other ways to specify sequences (right now, only characters are supported)
    * Find a better way to prepare data for tensorflow
    * Find a way to shuffle the data from the batch generator
    * Probably move downloading functionality into its own file once we support
      more than just LibriSpeech

"""

import numpy as np
import os

import urllib
import pickle
import json
import tarfile
import sys
import re

import argparse

import SimUGANSpeech.util.audio_util as audio_util
from SimUGANSpeech.util.data_util import chunkify
from SimUGANSpeech.definitions import LIBRISPEECH_DIR
from SimUGANSpeech.data.librispeechdata import POSSIBLE_FOLDERS


LIBRISPEECH_URL_BASE = "http://www.openslr.org/resources/12/{0}"

def _voice_txt_dict_from_path(folder_path):
    """Creates a dictionary between voice ids and txt file paths

    Walks through the provided LibriSpeech folder directory and 
    creates a dictionary, with voice_id as a key and all associated text files

    Args:
        folder_path (str): The path to the LibriSpeech folder
    
    Returns:
        dict : Keys are the voice_ids, values are lists of the paths to trans.txt files.

    """
    voice_txt_dict = {}

    for dir_name, sub_directories, file_names in os.walk(folder_path):
        if len(sub_directories) == 0: # this is a root directory
            file_names = list(map(lambda x: os.path.join(dir_name, x), file_names))
            txt_file = list(filter(lambda x: x.endswith('txt'), file_names))[0]

            voice_id = os.path.basename(dir_name)

            if voice_id not in voice_txt_dict:
                voice_txt_dict[voice_id] = [txt_file]
            else:
                voice_txt_dict[voice_id].append(txt_file)

    return voice_txt_dict

def _transcriptions_and_flac(txt_file_path):
    """Gets the transcriptions and .flac files from the path to a trans.txt file.

    Given the path to a trans.txt file, this function will return a list of 
    transcriptions and a list of the .flac files. Each flac file entry index corresponds 
    to the transcription entry index.

    Args:
        txt_file_path (str): The path to a trans.txt file

    Returns:
        list : A list of transcriptions
        list : A list of paths to .flac files
    """
    transcriptions = []
    flac_files = []

    parent_dir_path = os.path.dirname(txt_file_path)

    with open(txt_file_path, 'rb') as f:
        lines = [x.decode('utf8').strip() for x in f.readlines()]
    
    for line in lines:
        splitted = re.split(' ', line)
        file_name = splitted[0]
        transcriptions.append(" ".join(splitted[1:]))
        flac_files.append(os.path.join(parent_dir_path, "{0}.flac".format(file_name)))
 
    return transcriptions, flac_files 


def flacpath_transcription_id(folder_path):
    """Get a all .flac files, transcriptions, and ids in a path

    Args:
        folder_path (str): Path to the folder

    Returns:
        dict: Contains flac files, transcriptions, and ids

    """
    voice_txt_dict = _voice_txt_dict_from_path(folder_path)
    
    flac_files = []
    transcriptions = []
    ids = []

    for voice_id in voice_txt_dict:
        txt_files = voice_txt_dict[voice_id]
        for txt_file in txt_files:
            t, flacs = _transcriptions_and_flac(txt_file)
            flac_files += flacs
            transcriptions += t
            ids += [voice_id] * len(flacs)

    return {'paths': flac_files, 'transcriptions': transcriptions, 'ids': ids}


def _print_download_progress(count, block_size, total_size):
    """Print the download progress.

    Used as a callback in _maybe_download_and_extract.

    """
    pct_complete = float(count * block_size) / total_size
    msg = "\r- Download progress: {0:.1%}".format(pct_complete)

    sys.stdout.write(msg)
    sys.stdout.flush()


def _maybe_download_and_extract(folder_dir, folder_names, verbose):
    """Download and extract data if it doesn't exist.
    
    Args:
        folder_dir (str): The path to LibriSpeech 
        folder_paths (list of str): List of the folder names
            (e.g., dev-clean, dev-test, etc.)
        verbose (bool): Whether or not to print progress

    """

    if not os.path.exists(folder_dir):
        if verbose:
            print ("{0} doesn't exist. Making now.".format(folder_dir))
        os.makedirs(folder_dir)

    for fname in folder_names:
        if not os.path.exists(os.path.join(folder_dir, fname)):
            tar_file_name = fname + ".tar.gz"
            tar_file_path = os.path.join(folder_dir, tar_file_name)
            url = LIBRISPEECH_URL_BASE.format(tar_file_name)
            
            if verbose:
                print ("{0} not found. Downloading {1}".format(fname, tar_file_name))

            if verbose:
                print (url)
                file_path, _ = urllib.request.urlretrieve(url=url,
                                                          filename=tar_file_path,
                                                          reporthook=_print_download_progress)
                print ()
                print ("Download complete. Extracting {0}".format(tar_file_path))
            else:
                file_path, _ = urllib.request.urlretrieve(url=url,
                                                          filename=tar_file_path)
            tarfile.open(name=tar_file_path, mode="r:gz").extractall(os.path.join(folder_dir, '..'))
        else:
            if verbose:
                print ("{0} found. Skipping download...".format(fname))



def librispeech_initialize(folder_dir,
                           folder_names,
                           save_folder,
                           verbose):
    """Download LibriSpeech data, preprocess and save 

    For specified LibriSpeech datasets, extract:
    - transcriptions
    - ids 
    - flac paths

    All of this is saved into a dict 
    Assuming we're processing dev-clean at /path/to/dev-clean, 

    {save_folder}/dev-clean/transcriptions.pkl
    {save_folder}/dev-clean/ids.pkl
    {save_folder}/dev

    A master file is saved as well that specifies information about preprocessing.
    This is saved to /path/to/dev-clean/master.pkl.

    Args:
        folder_dir (str): The path to LibriSpeech 
        folder_paths (list of str): List of the folder names
            (e.g., dev-clean, dev-test, etc.)
        save_folder (str): The path to the destination to save pkl data
        verbose (bool): Whether or not to print progress

    """
    for fname in folder_names:
        if verbose:
            print ("Processing {0}".format(fname))
        fpath = os.path.join(folder_dir, fname)
        master_file_path = os.path.join(fpath, 'master.pkl')
        if not os.path.exists(fpath):
            raise ValueError("{0} does not exist. Make sure you download the data first.".format(fpath))
        data = flacpath_transcription_id(fpath)
        pickle.dump(data, open(master_file_path, 'wb'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script used to preprocess Librispeech data.")

    # Options to download and generate spectrograms
    parser.add_argument("--clean", action='store_true',
                        help="Delete all existing processed data (but don't delete LibriSpeech folder)")

    # Options for which folders to use
    for folder in POSSIBLE_FOLDERS: 
        parser.add_argument("--{0}".format(folder), action='store_true',
                            help="Include {0}".format(folder))

    parser.add_argument("--all", action='store_true',
                        help="Include all possible folders")

    # Verbosity
    parser.add_argument("--verbose", action='store_true',
                        help="Verbosity")

    # Process Parameters
    args = parser.parse_args()

    folder_dir = LIBRISPEECH_DIR
    folder_names = []

    # Get all paths to LibriSpeech data
    if args.all:
        folder_names = POSSIBLE_FOLDERS
    else:
        for folder in POSSIBLE_FOLDERS:
            # Optional arguments mess up the folder names.
            folder_key = folder.replace("-", "_") 
            if vars(args)[folder_key]:
                folder_names.append(folder)

    if args.verbose:
        print ("Processing: ")
        for fname in folder_names:
            print ("- {0}".format(fname))

    save_dir = LIBRISPEECH_DIR
    if args.clean:
        # Delete all of the saves that we have already
        if args.verbose:
            print ("Cleaning the directory...")
            print ("Files being deleted:")
        for fname in folder_names:
            fpath = os.path.join(save_dir, fname)
            if os.path.exists(fpath):
                pkl_files = [os.path.join(save_dir, fname, f) for f in os.listdir(fpath) if f.endswith(".pkl")]
                for f in pkl_files:
                    if args.verbose:
                        print ("{0}".format(f))
                    os.remove(f)
        if args.verbose:
            print ("Completed cleaning process.")

    if args.verbose:
        print ("-----------------------------------")
        print ("Downloading/extracting if necessary")
    _maybe_download_and_extract(folder_dir, folder_names, args.verbose)

    if args.verbose:
        print ("-----------------------------------")
        print ("Beginning initialization")
    librispeech_initialize(folder_dir, folder_names, save_dir, args.verbose)
