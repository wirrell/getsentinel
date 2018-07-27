"""Extracts data from Sentinel products for given regions of interest.

Postage stamp ROIs out of given rasters file in batch. After processing the
Stacker object acts as a dictionary from which numpy arrays containing all the
multi-temporal data layers.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.

Note
----
Currently only handles Sentinel-1 products.

Attributes
----------
S1_RASTER_PATH : str
    Local path within a Sentinel-1 .SAFE file to the measurement rasters.


TODO
----
Implement S2 product handling.
Implement other band_list preferences in `run` and `set_bands`
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
    """Creates stacks of arrays from a product list and a group of shape files.

    Arrays contains the raster data each passed shapefile over Sentinel
    products covering different dates/times.

    Note
    ----
    The user does not need to concern themselves with checking that the
    products passed contain data for for all the shapefiles. This class will
    sort products to their corresponding shapefiles and filter out all null
    data.

    Parameters
    ----------
    product_list : dict
        Contains the Sentinel products containing data relevant to the
        area coverered by the passed shapefiles.
    shape_files : list
        A `list` of `str` containing the paths to all of the relevant
        shapefiles.
    start_date : datetime.date
        The start of the time period used for data extraction. Any Sentinel
        products passed to the `Stacker` but generated outside of this time
        period will be excluded from the extraction process.
    end_date : datetime.date
        The end of the time period used for data extraction. Inclusive.

    Attributes
    ----------
    products : dict
        Filtered copy of `product_list` passed to the object containing only
        products generated between `start_date` and `end_date`.
    product_boundaries : dict
        Contains `shapely.geometry.Polygon` objects describing the boundaries
        of each of the products in `products`.
    shape_files : list
        Contains a copy of `shape_files` passed to the object.
    start_date : datetime.date
        A copy of `start_date` passed to the object.
    end_date : datetime.date
        A copy of the `end_date` passed to the object.
    job_list : dict
        Contains keys of all the uuids of products passed to the object, with
        their values being the shapefiles that are within the boundaries of
        each product.
    stack_list : dict
        After the `run` method is called, this `dict` is populated with keys
        that are the names of the shapefiles passed, with their values being
        the corresponding processed `numpy` arrays.
    band_list : list
        `list` of `str` containing the product bands that are to be extracted
        from the products.

    """

    def __init__(self,
                 product_list,
                 shape_files,
                 start_date,
                 end_date):

        self.shape_files = shape_files
        self.start_date = start_date
        self.end_date = end_date
        # filters the product list and generates the shapely objects for the products
        self.products, self.product_boundaries = self._gen_product_shapes(
            product_list)
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

    def set_bands(self, s1_band_list=[], s2_band_list=[]):
        """Sets the attribute `band_list` to the passed bands.

        Valid bands for S1 GRD products there are: 'vv', 'vh'.

        Note
        ----
        Currently only supports S1 GRD products

        Parameters
        ----------
        s1_band_list : list
            `list` of `str` containing the S1 bands the user wants extract from
            the S1 products passed to `Stacker`.
            Required form : ['band1', 'band2', ... ]
        s2_band_list : list
            `list` of `str` containing the S2 bands the user wants extract from
            the S2 products passed to `Stacker`.
            Required form : ['band1', 'band2', ... ]

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the band strings passed are not valid bands.

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

    def run(self):
        """Runs the data layer extraction and stacking process.

        Note
        ----
        Currently only supports Sentinel-1 products.

        Returns
        -------
        None

        Raises
        ------
        NotImplementedError
            If S2 products have been passed to `Stacker`.
        ValueError
            If `set_bands` has not been called before calling `run`.
        ValueError
            If any products other than S1 or S2 products are passed to
            `Stacker`.

        """

        platforms = [self.products[uuid]['platformname'] for uuid in
                     self.products]
        for platform in platforms:
            if platform != 'Sentinel-1':
                raise NotImplementedError("Currently only supports Sentinel-1"
                                          " products.")
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
                                   constant_values=np.NAN)
                    width_add = width_add - 1
                    continue
                # pad left side of array
                layer = np.pad(layer,
                               ((0, 0), (1, 0)),
                               'constant',
                               constant_values=np.NaN)
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

                # mask all the zero values in the output array sounding the
                # region of interest
                out_image = np.ma.masked_where(out_image==0, out_image)

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
        filtered_products = {}

        # ESA product footprints are in WGS84 (epsg: 4326)
        for uuid, product in product_list.items():
            product_start = datetime.datetime.strptime(
                                                product['beginposition'][:10],
                                                '%Y-%m-%d').date()
            if self.start_date <= product_start <= self.end_date:
                product_shape = shapely.wkt.loads(product['footprint'])
                product_boundaries[uuid] = product_shape
                filtered_products[uuid] = product


        return filtered_products, product_boundaries

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

    Parameters
    ----------
    input_array : numpy.ndarray
        An existing array that is to be converted to an `InfoLayer`.
    info : list, str
        `list` of `str` or just `str` that contains info on each layer such as
        UUID of origin, platform, date of capture, band, and processing level.
    tranform : affline.Affline
        the out_transform output from the `mask` function of the `rasterio`
        library.
    name : str, optional
        The name of the InfoLayer. Used in the final array stacks to name the
        stacks with the `str` of their corresponding shapefile names.

    Attributes
    ----------
    info : list, str
        Copy of parameter `info`.
    tranform : affline.Affline
        Copy of parameter `transform`.
    name : str, optional
        Copy of paramter `name`.

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
