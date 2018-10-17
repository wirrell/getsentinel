"""Extracts data from Sentinel products for given regions of interest.

Postage stamp ROIs out of given rasters file in batch. After processing the
Stacker object acts as a dictionary from which numpy arrays containing all the
multi-temporal data layers.

Handles both Sentinel-1 and Sentinel-2 rasters over multiple time frames.

Example
-------

    from getsentinel import gs_localmanager, gs_stacker

    products = gs_localmanager.get_product_inventory()

    roi = 'path/to/test_field.geojson' 
    start = datetime.date(2018, 5, 6)
    end = datetime.date(2018, 5, 7)

    stacker = gs_stacker.Stacker(products, roi, start, end)

    # get the True Colour Image at resolution 10m
    stacker.set_bands(s2_band_list=['TCI'], s2_resolution=10)

    data = stacker.generate_stacks()


"""
# TODO
# ----
# Investigate doing the masking using `gdal` instead of `rasterio`.
# Revisit non-uniform arrays after masking. Is it fixed after applying orbit
# files in gpt?

from . import gs_config
import datetime
import warnings
from pathlib import Path
import numpy as np
import shapely
import shapefile
import rasterio
import rasterio.mask
from osgeo import osr, ogr


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
        area coverered by the passed shapefiles or geojsons.
    geo_files : list or str
        A `list` of `str` containing the paths to all of the relevant
        shapefiles or geojsons or a single `str`.
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
    geo_files : list
        Contains a copy of `geo_files` passed to the object.
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
                 geo_files,
                 start_date,
                 end_date):

        self.geo_files = geo_files
        self.start_date = start_date
        self.end_date = end_date
        # filters the product list and generates the shapely objects
        # for the products
        self.products, self.product_boundaries = self._gen_product_shapes(
            product_list)
        # generates the shapely objects for the ROIs
        if type(geo_files) is str:
            geo_files = [geo_files]
        self._gen_ROI_shapes(geo_files)
        # holds the uuids and corresponding shape files within each product
        self.job_list = self._allocate_ROIs()
        # lists all the names of the shapefiles
        self.stack_list = {name: {} for name in self.ROIs}
        # temporary store for the layers before final combination
        self._layerbank = {name: {} for name in self.stack_list}
        self.band_list = False
        self.weather_check = False

    def set_bands(self, s1_band_list=[], s2_band_list=[], s2_resolution=False):
        """Sets the attribute `band_list` to the passed bands.

        Valid bands for S1 GRD products there are: 'vv', 'vh'.
        Valid bands for S2 L2A products are:

          '10': ['AOT', 'B02', 'B03', 'B04', 'B08', 'TCI',
                 'WVP'],
          '20': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                 'B07', 'B8A', 'B11', 'B12', 'SCL', 'TCI',
                 'WVP'],
          '60': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                 'B07', 'B8A', 'B09', 'B11', 'B12', 'SCL',
                 'TCI', 'WVP']}

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
        s2_resolution : int, optional
            Choose the band resolution of the Sentinel-2 bands. Can be `10`,
            `20`, or `60`.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the band strings passed are not valid bands.

        """

        # TODO: implement S2 bands as valid

        if s2_band_list and s2_resolution not in [10, 20, 60]:
            RuntimeError("You must specify a resolution of int 10, 20, or 60"
                         " when stacking Sentinel-2 products.")

        s1_valid_bands = ['vv', 'vh']
        s2_valid_bands = {'10': ['AOT', 'B02', 'B03', 'B04', 'B08', 'TCI',
                                 'WVP'],
                          '20': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                                 'B07', 'B8A', 'B11', 'B12', 'SCL', 'TCI',
                                 'WVP'],
                          '60': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                                 'B07', 'B8A', 'B09', 'B11', 'B12', 'SCL',
                                 'TCI', 'WVP']}
        if s2_resolution:
            s2_valid_bands = s2_valid_bands[str(s2_resolution)]

        if s1_band_list and s2_resolution:
            warnings.warn("Sentinel-1 GRD products are 10m resolution pixels."
                          " Combining Sentinel-2 products with resolution of"
                          " 20m or 60m with Sentinel-1 products will result in"
                          " incoherent data output at the per-pixel level.")

        for band in s1_band_list:
            if band not in s1_valid_bands:
                print(self.set_bands.__doc__)
                raise ValueError('Passed bands not in valid band list.')
        for band in s2_band_list:
            if band not in s2_valid_bands:
                print(self.set_bands.__doc__)
                raise ValueError('Passed bands not in valid band list.')

        bands = s1_band_list + s2_band_list

        for roi in self._layerbank:
            for band in bands:
                self._layerbank[roi][band] = {}

        self.band_list = [s1_band_list, s2_band_list]

        if s2_resolution:
            self.s2_res = s2_resolution

    def generate_stacks(self):
        """Runs the data layer extraction and stacking process.

        Returns
        -------
        dict
            Contains all the generate `Stack` objects keyed by the names of
            their corresponding shapefiles.


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
            if platform not in ['Sentinel-1', 'Sentinel-2']:
                raise NotImplementedError("Currently only supports Sentinel-1"
                                          " and Sentinel-2 products.")
        if not self.band_list:
            raise ValueError("Please set the band list via"
                             " .set_bands(band_list) before running.")

        for uuid, product in self.products.items():
            # get the filepath for the product files in .SAFE
            if product['platformname'] == 'Sentinel-1':
                band_list = self.band_list[0]
            elif product['platformname'] == 'Sentinel-2':
                if '2A' not in product['producttype']:
                    print("Product {0} is not processed to L2A, skipping."
                          "".format(product['identifier']))
                    continue
                band_list = self.band_list[1]
            else:
                raise ValueError("Unrecognised platform name in product {0}"
                                 "".format(product['identifier']))

            # extract bands from processed files
            for band in band_list:
                self._extract_data(uuid, band)

        self._generate_stacks()

        if self.weather_check:
            self._weather_report()

        return self.stack_list

    def _generate_stacks(self):
        """Make the layers uniform and combine them into numpy array stacks."""

        for roi, bands in self._layerbank.items():
            for band, layers in bands.items():
                layers_ = [layer for date, layer in sorted(layers.items())]
                info_ = [layer.info for date, layer in sorted(layers.items())]
                transforms_ = [layer.transform for date, layer in
                               sorted(layers.items())]
                layers_ = self._pad_layers(layers_)
                if len(layers_) is 0:
                    print("No data for ROI {0} in band {1} for the given"
                          " products.".format(roi, band))
                    continue
                stack = np.stack(layers_, axis=0)
                stack = np.ma.masked_where(stack == 0, stack)
                stack = Stack(stack, info_, transforms_, roi)
                # mask all the zero values in the output array sounding the
                # region of interest
                self.stack_list[roi][band] = stack

    def _pad_layers(self, layers):
        """Pads the layers with zeroes so they conform to a uniform shape."""

        padded_layers = []

        height_max = 0
        width_max = 0
        for layer in layers:
            depth, height, width = layer.shape
            if height > height_max:
                height_max = height
            if width > width_max:
                width_max = width

        for layer in layers:
            depth, height, width = layer.shape
            height_add = height_max - height
            width_add = width_max - width

            while width_add:
                if width_add % 2 is 0:
                    # pad right side of array
                    layer = np.pad(layer,
                                   ((0, 0), (0, 0), (0, 1)),
                                   'constant',
                                   constant_values=np.NAN)
                    width_add = width_add - 1
                    continue
                # pad left side of array
                layer = np.pad(layer,
                               ((0, 0), (0, 0), (1, 0)),
                               'constant',
                               constant_values=np.NaN)
                width_add = width_add - 1

            while height_add:
                if height_add % 2 is 0:
                    # pad top of array
                    layer = np.pad(layer,
                                   ((0, 0), (1, 0), (0, 0)),
                                   'constant',
                                   constant_values=0)
                    height_add = height_add - 1
                    continue
                # pad bottom of array
                layer = np.pad(layer,
                               ((0, 0), (0, 1), (0, 0)),
                               'constant',
                               constant_values=0)
                height_add = height_add - 1

            padded_layers.append(layer)

        return padded_layers

    def check_weather(self, cloud=False, snow=False):
        """
        Set a threshold for the probability of cloud or snow cover in the
        region of interest.

        If the probability cover provided by the ESA in the automated cloud and
        snow masks is higher than the user-defined threshold, a warning is
        thrown during stacking.

        Parameters
        ----------
        cloud : int, optional
            The percentrage threshold cloud probability for regions of
            interest, above which the stacker throws a warning.
        snow : int, optional
            The percentrage threshold snow probability for regions of
            interest, above which the stacker throws a warning.

        Returns
        -------
        None
        """

        for threshold in (cloud, snow):
            if threshold and (threshold < 0 or threshold > 100):
                raise ValueError("Please enter an int between 0 and 100")

        self.weather_check = True
        self.cloud_info = {ROI: [] for ROI in self.ROIs}
        self.snow_info = {ROI: [] for ROI in self.ROIs}
        self.weather_thresholds = {'cloud': cloud, 'snow': snow}

    def _weather_concealment(self, mask, tilepath, ROI, filename, datetime):
        """Checks the percentage likelihood of weather concealment using the
        ESA provided masks."""

        cloud_threshold = self.weather_thresholds['cloud']
        snow_threshold = self.weather_thresholds['snow']

        qi_data = tilepath.joinpath('QI_DATA')
        cloud_mask = list(qi_data.glob('*CLD*20m.jp2'))
        snow_mask = list(qi_data.glob('*SNW*20m.jp2'))
        if len(cloud_mask) is not 1:
            raise RuntimeError("Could not locate the cloud mask for {0}"
                               "".format(filename))
        if len(snow_mask) is not 1:
            raise RuntimeError("Could not locate the snow mask for {0}"
                               "".format(filename))
        cloud_mask = cloud_mask[0]
        snow_mask = snow_mask[0]

        if cloud_threshold:
            with rasterio.open(str(cloud_mask), 'r') as cloud:
                out_image, out_transform = rasterio.mask.mask(cloud,
                                                              mask,
                                                              crop=True)
                if np.max(out_image) >= cloud_threshold:
                    if datetime not in self.cloud_info[ROI]:
                        self.cloud_info[ROI].append(datetime)

        if snow_threshold:
            with rasterio.open(str(snow_mask), 'r') as snow:
                out_image, out_transform = rasterio.mask.mask(snow,
                                                              mask,
                                                              crop=True)
                if np.max(out_image) >= snow_threshold:
                    if datetime not in self.snow_info[ROI]:
                        self.snow_info[ROI].append(datetime)

    def _weather_report(self):
        """Prints the results of the weather check to the console."""

        cloud_threshold = self.weather_thresholds['cloud']
        snow_threshold = self.weather_thresholds['snow']

        print("\ngs_stacker WEATHER CHECK RESULTS:\n")

        if cloud_threshold:
            print("The following ROIs have CLOUD cover probability above the"
                  " specified {0}% threshold on these dates:\n"
                  "".format(cloud_threshold))
            for roi in self.cloud_info:
                print("{0}:".format(roi))
                if len(self.cloud_info[roi]) is 0:
                    print("         ", "NONE")
                for datet in self.cloud_info[roi]:
                    print("         ", datet)

        if snow_threshold:
            print("The following ROIs have SNOW cover probability above the"
                  " specified {0}% threshold on these dates:\n"
                  "".format(snow_threshold))
            for roi in self.snow_info:
                print("{0}:".format(roi))
                if len(self.snow_info[roi]) is 0:
                    print("         ", "NONE")
                for datet in self.snow_info[roi]:
                    print("         ", datet)
            print("\n")

    def _extract_data(self, uuid: str, band: str):
        """
        Checks the joblist to see what ROIs need to be postage stamped out of
        the given uuid and extracts them using rasterio.mask.

        Saves the product metadata to each ROI's extracted numpy array and
        add it to the corresponding list in the layer_stack.
        """

        product = self.products[uuid]
        platform = product['platformname']
        filename = product['filename']
        datetime = product['beginposition'],
        info = {'from': uuid,
                'platform': platform,
                'datetime': datetime,
                'band': band,
                'processing': product['producttype']}

        if platform == 'Sentinel-2':
            data_path = Path(gs_config.DATA_PATH)
            file_path = data_path.joinpath(filename)
            granule = file_path.joinpath('GRANULE')
            for child in granule.iterdir():
                # should be only one sub-dir in the GRANULE dir
                if child.is_dir():
                    tilepath = child
                    break
            img_data = tilepath.joinpath('IMG_DATA')
            ext = 'R{0}m'.format(str(self.s2_res))
            raster_dir = img_data.joinpath(ext)
            for child in raster_dir.iterdir():
                if band in str(child):
                    proc_file = child
                    break

        if platform == 'Sentinel-1':
            if filename.endswith('.SAFE'):
                raise RuntimeError("Product {0} is an unprocessed Sentinel-1 "
                                   "file and cannot be stacked.".format(
                                    filename))
            info['mode'] = product['sensoroperationalmode']
            if band is 'vv':
                layer_number = 0
            if band is 'vh':
                layer_number = 1

            proc_file = Path(gs_config.DATA_PATH).joinpath(filename)

        # get the shape the reside within this product
        associated_ROIs = self.job_list[uuid]

        def reproject_ROI(mask, epsg):
            # Reproject the roi coords to the same crs as the raster
            roi = mask[0]
            wgs84 = osr.SpatialReference()
            wgs84.ImportFromEPSG(4326)
            raster_crs = osr.SpatialReference()
            raster_crs.ImportFromEPSG(epsg)
            shape_ = ogr.CreateGeometryFromWkt(roi.wkt)
            transform = osr.CoordinateTransformation(wgs84, raster_crs)
            shape_.Transform(transform)
            # back to shapely
            roi = shapely.wkt.loads(shape_.ExportToWkt())
            return [roi]

        with rasterio.open(str(proc_file), 'r') as raster:
            raster_epsg = raster.crs.to_epsg()

            # for all of the corresponding ROIs related to this product
            for ROI in associated_ROIs:
                mask = [self.ROIs[ROI]]  # rasterio requires mask in iterable

                # reproject the mask to the raster epsg if it is not WGS84
                if raster_epsg is not 4326:
                    mask = reproject_ROI(mask, raster_epsg)

                # if we need to check the weather cover for Sentinel-2 products
                if self.weather_check and '2' in platform:
                    self._weather_concealment(mask, tilepath, ROI, filename,
                                              datetime)

                out_image, out_transform = rasterio.mask.mask(raster,
                                                              mask,
                                                              crop=True)

                if np.count_nonzero(out_image) is 0 or (np.max(out_image) <
                                                        0.0001):
                    # The mask has fallen victim the the traversty that is ESA
                    # polygons being actually sligthly larger than the product
                    # data they represent. Ie. the ROI is in the dead zone!
                    continue

                if '1' in platform:
                    # out_image is 3D when ie. [2, X, Y] and we only need 2D
                    # either vv or vh
                    if out_image.shape[0] is not 1:
                        layers = np.split(out_image, 2)
                        layer = Stack(layers[layer_number], info,
                                      out_transform)
                    else:
                        layer = Stack(out_image, info,
                                      out_transform)

                if '2' in platform:
                    layer = Stack(out_image, info, out_transform)

                date = product['beginposition']
                self._layerbank[ROI][band][date] = layer

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

    def _gen_ROI_shapes(self, geo_files):
        """Loads shapely objects from given geo files."""

        # set WGS84 spatial ref
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)

        ROIs = {}  # stores the referenced shapely objects use for masking

        for geo_file in geo_files:
            geo_file = Path(geo_file)
            suffix = geo_file.suffix
            if suffix not in ['.shp', '.geojson']:
                raise TypeError("File {0} not supported by gs_stacker.Stacker."
                                " Only .shp and .geojson files are currently"
                                " supported for defining masks / ROIs".format(
                                    geo_file))
            filename = geo_file.stem
            x_coords = []
            y_coords = []
            shp = ogr.Open(str(geo_file))
            if shp.GetLayerCount() > 1:
                warnings.warn("geo-referenced files (.shp, .geojson etc)"
                              " with more than one layer / feature will have"
                              " the coordinates of all layers / features used"
                              " to generate a mask for the Sentinel file.")
            layer = shp.GetLayer()
            shp_crs = layer.GetSpatialRef()
            if shp_crs is None:  # means the file has not been georeferenced
                raise RuntimeError("Could not retrieve the co-ordinate"
                                   " reference system data from the meta"
                                   " data of the geo-file {0}.\n"
                                   " The file may not be correctly"
                                   " georeferenced.".format(geo_file))
            transform = osr.CoordinateTransformation(shp_crs, wgs84)

            if suffix == '.shp':
                shp = shapefile.Reader(str(geo_file))
                # extract all points from all shapes
                for shape in shp.shapes():
                    for point in shape.points:  # in the file
                        x_coords.append(point[0])
                        y_coords.append(point[1])
                coords = list(zip(x_coords, y_coords))
                m = shapely.geometry.MultiPoint(coords)  # import into shapely
                extents = m.convex_hull  # gets polygon that encomps all points
                shape_ = ogr.CreateGeometryFromWkt(extents.wkt)

            if suffix == '.geojson':
                geometries = []
                for layer in shp:
                    for i in range(layer.GetFeatureCount()):
                        feature = layer.GetFeature(i)
                        geometries.append(feature.geometry())
                shape_ = geometries[0]
                for i in range(1, len(geometries)):
                    shape_ = shape_.AddGeometry(geometries[i])

            # now reproject in ogr
            shape_.Transform(transform)
            # back to shapely for boundary comparison during run()
            shape = shapely.wkt.loads(shape_.ExportToWkt())

            ROIs[filename] = shape

        self.ROIs = ROIs


class Stack(np.ndarray):
    """Used to add an attribute to an existing numpy array.
    adapted from:
    https://docs.scipy.org/doc/numpy-1.12.0/user/basics.subclassing.html

    Also masks all the zero values out of the array.

    Parameters
    ----------
    input_array : numpy.ndarray
        An existing array that is to be converted to a `Stack`.
    info : list, str
        `list` of `str` or just `str` that contains info on each layer such as
        UUID of origin, platform, date of capture, band, and processing level.
    tranform : affline.Affline
        the out_transform output from the `mask` function of the `rasterio`
        library.
    name : str, optional
        The name of the Stack. Used in the final array stacks to name the
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
        obj = np.ma.masked_where(obj == 0, obj)
        obj.info = info
        obj.transform = transform
        if name:
            obj.name = name
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.info = getattr(obj, 'info', None)
