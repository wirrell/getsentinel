"""
gs_stacker.py

Postage stamp ROIs out of given rasters file in batch.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.

NOTE: Currently only handles Sentinel-1 products.
"""

from . import gs_config
import datetime
from pathlib import Path
import json
import shapely
import shapefile
import rasterio
import rasterio.mask
from osgeo import osr, ogr, gdal

S1_RASTER_PATH = '/measurement/'  # where .tiff files reside in S1 .SAFE

class Stacker():

    """
    Takes a product list and a group of shape files and creates stacks of numpy
    arrays that contain the raster data for each of the ROIs specified by
    individual shape files.
    """

    def __init__(self, product_list: dict, shape_files: list):

        self.products = product_list
        self.shape_files = shape_files
        self._get_product_shapes(product_list)
        self._get_ROI_shapes(shape_files)
        self.start_date = False
        self.end_date = False

    def set_date_limit(self,
                       start_date: datetime.date,
                       end_date: datetime.date):

        """Set an optional date period from which to stamp out date."""

        self.start_date = start_date
        self.end_date = end_date

    def run(self, date_coherency: bool = False):

        """
        Runs the stacking process.
        NOTE: If date_coherency = True, the follow format occurs:
            If shapefileA has products for day1, day2, day3, and day4 and
            shapefileB has products for only day1, day2, and day4 then
            shapefileB will be have any zeroes entry in its stack for day3 for
            date coherency, otherwise it will only have 3 entries.
        """

        platforms = [self.products[uuid]['platformname'] for uuid in
                     self.products]
        for platform in platforms:
            if platform != 'Sentinel-1':
                raise NotImplementedError("Currently only supports Sentinel-1"
                                          " products.")

        for uuid, product in self.products.items():
            product_path = gs_config.DATA_PATH + product['filename']
            measurements_folder = product_path + S1_RASTER_PATH
            measurements_folder = Path(measurements_folder)
            for f in measurements_folder.iterdir():
                pass

    def _get_product_shapes(self, product_list: dict):

        """Loads shapely objects from product WKT footprints."""

        product_boundaries = {}

        # ESA product footprints are in WGS84 (epsg: 4326)
        for uuid, product in product_list.items():
            product_shape = shapely.wkt.loads(product['footprint'])
            product_boundaries[uuid] = product_shape

        self.product_boundaries = product_boundaries


    def _get_ROI_shapes(self, shape_files):

        """Loads shapely objects from given shape files."""

        # set WGS84 spatial ref
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)


        ROIs = {}  # stores the referenced files use for masking
        ROI_shapes = {}  # stores the shapely files used to allocating

        for shape_file in shape_files:
            filename = shape_file.split('/')[-1][:-4]
            print(filename)
            shp = ogr.Open(shape_file)
            layer = shp.GetLayer()
            shp_crs = layer.GetSpatialRef()
            if shp_crs == wgs84:  # if already WGS84 - skip
                continue
            transform = osr.CoordinateTransformation(shp_crs, wgs84)
            x_coords = []
            y_coords = []
            shp = shapefile.Reader(shape_file)
            for shape in shp.shapes():  # extract all points from all shapes
                for point in shape.points:  # in the file
                    x_coords.append(point[0])
                    y_coords.append(point[1])
            coords = list(zip(x_coords, y_coords))
            m = shapely.geometry.MultiPoint(coords)  # import into shapely module
            extents = m.convex_hull  # gets small polygon that encomps all points
            # now reproject in ogr
            shape_ = ogr.CreateGeometryFromWkt(extents.wkt)
            shape_.Transform(transform)
            # into geoJson format for use in rasterio
            shape_geojson = json.loads(shape_.ExportToJson())

            ROI_shapes[filename] = extents
            ROIs[filename] = shape_geojson





