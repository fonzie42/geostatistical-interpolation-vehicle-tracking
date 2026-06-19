"""
Preprocessing pipeline for geostatistical interpolation of vehicle tracking
connectivity data. Converts raw GPS binary observations (online/offline) into
spatially aggregated proportions suitable for Kriging with ExaGeoStatCPP.
"""

from preprocessing.config import PipelineConfig
from preprocessing.spatial_binning import SpatialBinner
from preprocessing.pipeline import run_pipeline
from preprocessing.kriging import MaternParams, kriging_predict, load_csv_data
from preprocessing.exageostat_driver import RPredictor, RPredictionResult
