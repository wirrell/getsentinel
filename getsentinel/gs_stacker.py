"""
gs_stacker.py

Postage stamp ROIs out of given rasters file in batch.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.

NOTE: Currently only handles Sentinel-1 products.


TODO:
    Implement S2 product handling.
    Implement other band_list preferences in run()
    Implement data coherency functionality
    Speak to Joe about implemented geocode GDAL warp in the preprocessing
    module.
"""

from . import gs_config
import datetime
import subprocess
import warnings
from pathlib import Path
import numpy as np
import shapely
import shapefile
import rasterio
import rasterio.mask
import rasterio.errors as re
from osgeo import osr, ogr


S1_RASTER_PATH = '/measurement/'  # where .tiff files reside in S1 .SAFE


class Stacker():

    """
    Takes a product list and a group of shape files and creates stacks of numpy
    arrays that contain the raster data for each of the ROIs specified by
    individual shape files.
    """

    def __init__(self,
                 product_list: dict,
                 shape_files: list,
                 start_date: datetime.date,
                 end_date: datetime.date):

        self.products = product_list
        self.shape_files = shape_files
        self.start_date = start_date
        self.end_date = end_date
        # generates the shapely objects for the products
        self._gen_product_shapes(product_list)
        # generates the shapely objects for the ROIs
        self._gen_ROI_shapes(shape_files)
        # holds the uuids and corresponding shape files within each product
        self.job_list = self._allocate_ROIs()
        # lists all the names of the shapefiles
        self.stack_list = {name: None for name in self.ROIs}
        # temporary store for the layers before final combination
        self._layerbank = {name: {} for name in self.stack_list}
        self.band_list = False
        self._generated = False

    def __getitem__(self, key):

        """Implements dict like functionality."""

        if not self._generated:
            print("Please call the run method first.")
            return None

        return self.stack_list[key]

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
                # should only be one band file per band in Sentinel products

                self._extract_data(band_files[0], uuid, band)

        self._generate_stacks()

    def _generate_stacks(self):

        """Make the layers uniform and combine them into numpy array stacks."""

        np.set_printoptions(threshold=np.nan)
        for roi, layers in self._layerbank.items():
            layers_ = [layer for date, layer in sorted(layers.items())]
            info_ = [layer.info for date, layer in sorted(layers.items())]
            transforms_ = [layer.transform for date, layer in
                           sorted(layers.items())]
            layers_ = self._pad_layers(layers_)
            stack = np.stack(layers_, axis=0)
            stack = InfoLayer(stack, info_, transforms_, roi)
            self.stack_list[roi] = stack

        self._generated = True

    def _pad_layers(self, layers):

        """Pads the layers with zeroes so they conform to a uniform shape."""

        padded_layers = []

        height_max = 0
        width_max = 0
        for layer in layers:
            height, width = layer.shape
            if height > height_max:
                height_max = height
            if width > width_max:
                width_max = width

        for layer in layers:
            height, width = layer.shape
            height_add = height_max - height
            width_add = width_max - width

            while width_add:
                if width_add % 2 is 0:
                    # pad right side of array
                    layer = np.pad(layer,
                                   ((0, 0), (0, 1)),
                                   'constant',
                                   constant_values=0)
                    width_add = width_add - 1
                    continue
                # pad left side of array
                layer = np.pad(layer,
                               ((0, 0), (1, 0)),
                               'constant',
                               constant_values=0)
                width_add = width_add - 1

            while height_add:
                if height_add % 2 is 0:
                    # pad top of array
                    layer = np.pad(layer,
                                   ((1, 0), (0, 0)),
                                   'constant',
                                   constant_values=0)
                    height_add = height_add - 1
                    continue
                # pad bottom of array
                layer = np.pad(layer,
                               ((0, 1), (0, 0)),
                               'constant',
                               constant_values=0)
                height_add = height_add - 1

            padded_layers.append(layer)

        return padded_layers

    def _extract_data(self,
                      band_file: Path,
                      uuid: str,
                      band: str):

        """
        Checks the joblist to see what ROIs need to be postage stamped out of
        the given uuid and extracts them using rasterio.mask.

        Saves the product metadata to each ROI's extracted numpy array and
        add it to the corresponding list in the layer_stack.
        """

        with warnings.catch_warnings(record=True) as caught_warnings:
            raster = rasterio.open(str(band_file), 'r')
            raster_epsg = 'EPSG:' + str(raster.gcps[1]).split(':')[-1]
            raster.close()  # close file link so gdalwarp can modify the file

        # S1 products are georeferenced but no geocoded, so they return a
        # NotGeoreferencedWarning so must use gdalwarp
        # to introduce geocode for use in rasterio
        # TODO: Implement the geocoding in gs_preprocessing rather than here.
        if caught_warnings:
            if caught_warnings[0].category is re.NotGeoreferencedWarning:
                suffix = band_file.suffix
                file_path = str(band_file)[:-len(suffix)]
                new_file = file_path + '-geocoded' + band_file.suffix
                if not Path(new_file).exists():
                    print('Correcting georeferencing of file with'
                          ' UUID: {0}'.format(uuid))
                    gdal_command = ('gdalwarp -tps -r bilinear'
                                    ' -t_srs ' + raster_epsg +
                                    ' {0} {1}').format(str(band_file),
                                                       str(new_file))
                    # call gdalwarp in subprocess to geocode S1 file
                    try:
                        subprocess.run(gdal_command, shell=True)
                    except KeyboardInterrupt:
                        # Stop half-calculated rasters from taking up space
                        # upon keyboard interrupt.
                        Path(new_file).unlink()

                band_file = new_file

        # get the shape the reside within this product
        associated_ROIs = self.job_list[uuid]

        with rasterio.open(str(band_file), 'r') as raster:
            for ROI in associated_ROIs:
                mask = [self.ROIs[ROI]]  # rasterio requires mask in iterable
                out_image, out_transform = rasterio.mask.mask(raster,
                                                              mask,
                                                              crop=True)

                if np.count_nonzero(out_image) is 0 or np.amax(out_image) < 10:
                    # The mask has fallen victim the the traversty that is ESA
                    # polygons being actually sligthly larger than the product
                    # data they represent. Ie. the ROI is in the dead zone!
                    continue

                product = self.products[uuid]
                info = {'from': uuid,
                        'platform': product['platformname'],
                        'datetime': product['beginposition'],
                        'band': band,
                        'processing': product['producttype']}

                if product['platformname'] == 'Sentinel-1':
                    info['mode'] = product['sensoroperationalmode']

                # out_image is 3D when ie. [1, X, Y] and we only need the 2D
                layer = InfoLayer(out_image[0], info, out_transform)
                date = product['beginposition']
                self._layerbank[ROI][date] = layer

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
            product_start = datetime.datetime.strptime(
                                                product['beginposition'][:10],
                                                '%Y-%m-%d').date()
            if self.start_date <= product_start <= self.end_date:
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


class InfoLayer(np.ndarray):

    """Used to add an attribute to an existing numpy array.
    adapted from:
        https://docs.scipy.org/doc/numpy-1.12.0/user/basics.subclassing.html
    """

    def __new__(cls, input_array, info, transform, name=False):
        obj = np.asarray(input_array).view(cls)
        obj.info = info
        obj.transform = transform
        if name:
            obj.name = name
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.info = getattr(obj, 'info', None)
