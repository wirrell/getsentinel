"""
gs_stacker.py

Postage stamp ROIs out of given rasters file in batch.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.
"""

from . import gs_config

class Stacker():

    """
    Takes a product list and a group of shape files and creates stacks of numpy
    arrays that contain the raster data for each of the ROIs specified by
    individual shape files.


