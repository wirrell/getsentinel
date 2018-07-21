"""
gs_stacker.py

Postage stamp ROIs out of given rasters file in batch.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.

NOTE: Currently only handles Sentinel-1 products.


TODO:
    Implement S2 product handling.
    Implement other band_list preferences in run()
    Implement data coherency functionality
"""

from . import gs_config
import datetime
from pathlib import Path
import numpy as np
import shapely
import shapefile
import rasterio
import rasterio.mask
from osgeo import osr, ogr

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
        # generates the shapely objects for the products
        self._gen_product_shapes(product_list)
        # generates the shapely objects for the ROIs
        self._gen_ROI_shapes(shape_files)
        # holds the uuids and corresponding shape files within each product
        self.job_list = self._allocate_ROIs()
        # lists all the names of the shapefiles
        self.stack_list = [name for name in self.ROIs]
        # temporary store for the layers before final combination
        self._layerbank = {name: [] for name in self.stack_list}
        self.band_list = False
        self.start_date = False
        self.end_date = False

    def set_date_limit(self,
                       start_date: datetime.date,
                       end_date: datetime.date):

        """Set an optional date period from which to stamp out date."""

        self.start_date = start_date
        self.end_date = end_date

    def set_bands(self, s1_band_list: list = [], s2_band_list: list = []):

        """
        band_list is a list of strings containing the bands the user desires to
        be extracted from the product. For S1 GRD products there are: vv, vh

        Required form : ['band1', 'band2', ... ]

        """

        # TODO: implement S2 bands as valid

        s1_valid_bands = ['vv', 'vh']
        s2_valid_bands = []

        for band in s1_band_list:
            if band not in s1_valid_bands:
                print(self.set_bands.__doc__)
                raise ValueError('Passed bands not in valid band list.')
        for band in s2_band_list:
            if band not in s2_valid_bands:
                print(self.set_bands.__doc__)
                raise ValueError('Passed bands not in valid band list.')

        self.band_list = [s1_band_list, s2_band_list]

    def run(self, date_coherency: bool = False):

        """
        Runs the stacking process.


        NOTE: If date_coherency = True, the follow format occurs:
            If shapefileA has products for day1, day2, day3, and day4 and
            shapefileB has products for only day1, day2, and day4 then
            shapefileB will be have any zeroes entry in its stack for day3 for
            date coherency, otherwise it will only have 3 entries.
        """

        # TODO: implement date limits functionality
        # TODO: implement data coherency functionality

        platforms = [self.products[uuid]['platformname'] for uuid in
                     self.products]
        for platform in platforms:
            if platform != 'Sentinel-1':
                raise NotImplementedError("Currently only supports Sentinel-1"
                                          " products.")
        if date_coherency:
            raise NotImplementedError("Data coherency not yet implemented.")
        if not self.band_list:
            raise ValueError("Please set the band list via"
                             " .set_bands(band_list) before running.")

        for uuid, product in self.products.items():
            # get the filepath for the product files in .SAFE
            rasters_path = Path(gs_config.DATA_PATH + product['filename'] +
                                S1_RASTER_PATH)
            if product['platformname'] == 'Sentinel-1':
                band_list = self.band_list[0]
            elif product['platformname'] == 'Sentinel-2':
                band_list = self.band_list[1]
            else:
                raise ValueError("Unrecognised platform name in product {0}"
                                 "".format(product['identifier']))
            # generate a search term from the given band list
            for band in band_list:
                glob_find = '*' + band + '*'
            # get all the files for that band (should be just one)
                band_files = list(rasters_path.glob(glob_find))
                if band_files is 0:
                    print("No files found in product: {0} containing data for"
                          " band {1} - skipping.".format(product['identifier'],
                                                         band))
                    continue
                for band_file in band_files:
                    self._extract_data(band_file, uuid, band)

    def _extract_data(self, band_file: Path, uuid: str, band: str):

        """
        Checks the joblist to see what ROIs need to be postage stamped out of
        the given uuid and extracts them using rasterio.mask.

        Saves the product metadata to each ROI's extracted numpy array and
        add it to the corresponding list in the layer_stack.
        """

        # get the shape the reside within this product
        associated_ROIs = self.job_list[uuid]

        for ROI in associated_ROIs:
            mask = [self.ROIs[ROI]]  # rasterio requires mask in iterable
            print(self.product_boundaries[uuid].contains(self.ROIs[ROI]))
            with rasterio.open(str(band_file), 'r') as src:
                pass

            # TODO: implement masking procedure
            # NOTE: will need to fix crs read in for Sentinel-1 or develop work
            #       around.

    def _allocate_ROIs(self):

        """
        Checks product boundaries against ROI areas and allocates ROIs to
        products for stamping.
        """

        job_list = {}  # stores product UUIDs and accompanying ROIs

        for uuid, boundary in self.product_boundaries.items():
            uuid_jobs = []
            for ROI_name, shape in self.ROIs.items():
                if boundary.contains(shape):
                    uuid_jobs.append(ROI_name)
            job_list[uuid] = uuid_jobs

        return job_list

    def _gen_product_shapes(self, product_list: dict):

        """Loads shapely objects from product WKT footprints."""

        product_boundaries = {}  # stores the shapely files use for allocating

        # ESA product footprints are in WGS84 (epsg: 4326)
        for uuid, product in product_list.items():
            product_shape = shapely.wkt.loads(product['footprint'])
            product_boundaries[uuid] = product_shape

        self.product_boundaries = product_boundaries

    def _gen_ROI_shapes(self, shape_files):

        """Loads shapely objects from given shape files."""

        # set WGS84 spatial ref
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)

        ROIs = {}  # stores the referenced shapely objects use for masking

        for shape_file in shape_files:
            filename = shape_file.split('/')[-1][:-4]
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
            m = shapely.geometry.MultiPoint(coords)  # import into shapely
            extents = m.convex_hull  # gets polygon that encomps all points
            # now reproject in ogr
            shape_ = ogr.CreateGeometryFromWkt(extents.wkt)
            shape_.Transform(transform)
            # back to shapely for boundary comparison during run()
            shape = shapely.wkt.loads(shape_.ExportToWkt())

            ROIs[filename] = shape

        self.ROIs = ROIs
