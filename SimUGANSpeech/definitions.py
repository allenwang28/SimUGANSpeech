import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SRC_DIR, '..')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
LIBRISPEECH_DIR = os.path.join(DATA_DIR, 'LibriSpeech')
SYNTHETIC_DIR = os.path.join(DATA_DIR, 'synthetic_samples')
TENSORFLOW_DIR = os.path.join(DATA_DIR, 'tensorflow_models')
TF_LOGS_DIR = os.path.join(DATA_DIR, 'tensorflow_logs')
KERAS_DIR = os.path.join(DATA_DIR, 'keras_models')

