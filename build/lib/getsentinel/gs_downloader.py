"""getsentinel gs_downloader.py

Script to locate and auto-download products from Copernicus Open Access Hub
which contains ESA Sentinel Satellite products. https://scihub.copernicus.eu/
Queries and downloads are based on dates, coordinates, and product type.

Example
-------
Basic usage example::

    import datetime
    from getsentinel import gs_downloader

    shape_file = 'path/to/shapefile.shp'
    start = datetime.date(2018, 1, 1)
    end = datetime.date(2018, 6, 1)

    # initialise the query object
    query = gs_downloader.Query('S1', start, end, shape_file)
    query.product_details('L1', 'GRD', 'IW', 'VV VH')

    # initialise the hub connection
    hub = gs_downloader.CopernicusHubConnection()
    total_products, product_list = hub.submit_query(query)

    # optionally filter overlapping products from a given region
    # query.ROI contains a polygon generated from the input coordinates
    product_list = gs_downloader.filter_overlaps(product_list, query.ROI)

    # optinally download the corresponding product quicklooks
    hub.download_quicklooks(product_list)
    hub.download_products(product_list)

"""

# TODO
# ----
# Revise 'BEST' product filtering to use sets(?) / be more efficient

import datetime
import os
import xml.etree.ElementTree as ET
import warnings
import hashlib
import pathlib
import zipfile
import requests
from clint.textui import progress
import shapefile
import geojson
from shapely.geometry import MultiPoint, Polygon
from shapely.wkt import loads
from osgeo import ogr, osr
from . import gs_localmanager
from .gs_config import DATA_PATH, QUICKLOOKS_PATH, ESA_USERNAME, ESA_PASSWORD


class Query:
    """Holds the query parameters use in an ESA hub query.

    Parameters
    ----------
    sat : str
        Current Sentinel satellites supported: 'S1', 'S2'
    start_date : datetime.date
        The start date for the date range of the ESA query
    end_date : datetime.date, optional
        The end date for the date range of the ESA query
    ROI : str or list, optional
        Can be a `str` containing the path to a geo-referenced .geojson or
        shapefile or a list of coordinates, see the `set_coordinates` and
        `coords_from_file` methods for more information.

    Attributes
    ----------
    dates : tuple
        Contains the acquisition start and end datetime.date objects that
        define the query search time period.
    coordinates : list
        A list containing the coordinates of the boundary of the region of
        interest (ROI).
    tiles : tuple
        Contains a list of the ESA defined Sentinel-2 tiles that the ROI
        traverses and the tile which the ROI overlaps the most with in the
        format (overlapped_tiles, majority_tile).
    ROI : shapely.geometry.Polygon
        A shapely object defining the border of the region of interst using in
        the query.
    satellite : str
        Defines which Sentinel satellite the query is for, e.g. 'S1', 'S2'
    proclevel : str
        The processing level of the products desired from the query
    details : dict
        Contains optional parameters for the query

    """

    def __init__(self, satellite, start_date, end_date=False, ROI=False):

        self.acquisition_date_range(start_date, end_date)
        self.coordinates = False
        if ROI:
            self.set_coordinates(ROI)
        if satellite not in ['S1', 'S2']:
            raise ValueError(" Only Sentinel-1 (use 'S1') and Sentinel-2 (use"
                             " 'S2') products are currently supported.")
        self.satellite = satellite

    def acquisition_date_range(self, acqstart, acqend=False):
        """Set the date range for the query.

        This method will raise an error if a anything but datetime.date objects
        are passed to it or if acqstart is a date after acqend.

        Note
        ----
        This is used to specify the Sensing Start Time search criteria.
        If no end date is specific, the 24 hour period for the given
        start date is used. Any specified end date is considered
        inclusive.

        Parameters
        ----------
        acqstart : datetime.date
            The start date for the date range of the ESA query
        acqend : datetime.date, optional
            The end date for the date range of the ESA query

        Returns
        ------
        None

        """

        if type(acqstart) is not datetime.date:
            raise TypeError("You must pass a datetime.date object to this "
                            "method.")
        if acqend and type(acqend) is not datetime.date:
            raise TypeError("You must pass a datetime.date object to this "
                            "method.")
        if acqend and not (acqend >= acqstart):
            raise ValueError("The end acquisition date must be after the "
                             "beginning acquisition date.")

        self.dates = (acqstart, acqend)

    def coords_from_file(self, filepath):
        """Loads in the coordinates of a region of interest from a shapefile or
        geojson file.

        Uses the osgeo module to extract the coordinate reference system from
        the file and reprojects it to WGS84.

        Note
        ----
        Only geojson and shapefiles are currently supported.

        Parameters
        ----------
        filepath : str
            The path to the shapefile or geojson.

        Returns
        -------
        None

        """

        file_type = pathlib.Path(filepath).suffix

        if file_type not in ['.shp', '.geojson']:
            raise NotImplementedError('Currently only .shp and .geojson files'
                                      ' are supported.')

        # set WGS84 spatial ref
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)

        shp = ogr.Open(filepath)
        layer = shp.GetLayer()
        shp_crs = layer.GetSpatialRef()
        if shp_crs is None:  # means the file has not been georeferenced
            raise RuntimeError("Could not retrieve the co-ordinate"
                               " reference system data from the meta"
                               " data of the geo-file {0}.\n"
                               " The file may not be correctly"
                               " georeferenced.".format(filepath))

        x_coords = []
        y_coords = []

        if file_type == '.shp':
            shp = shapefile.Reader(filepath)
            for shape in shp.shapes():  # extract all points from all shapes
                for point in shape.points:  # in the file
                    x_coords.append(point[0])
                    y_coords.append(point[1])

        if file_type == '.geojson':
            with open(filepath, 'r') as f:
                gjson = geojson.load(f)
                if type(gjson) is geojson.feature.FeatureCollection:
                    features = gjson['features']
                    for feature in features:
                        coords = geojson.utils.coords(feature)
                        for coord in coords:
                            x_coords.append(coord[0])
                            y_coords.append(coord[1])
                else:
                    raise RuntimeError("Passed GeoJSON objects must be feature"
                                       " collections.")

        coords = list(zip(x_coords, y_coords))
        m = MultiPoint(coords)  # import into shapely
        shape_extents = m.convex_hull  # gets polygon that encomps all points
        if shp_crs != wgs84:  # if already WGS84 - skip
            transform = osr.CoordinateTransformation(shp_crs, wgs84)
            # now reproject in ogr
            shape_ = ogr.CreateGeometryFromWkt(shape_extents.wkt)
            shape_.Transform(transform)
            # back to shapely for easy coord extraction
            shape_extents = loads(shape_.ExportToWkt())
        coords = list(shape_extents.exterior.coords)

        self.set_coordinates(coords)

    def set_coordinates(self, coordlist):
        """Stores the passed coordinates and generates ROI boundary polygon.

        Stores the passed coordinates list and generates a shapely object
        describing the region of interest. Also uses the gs_gridtest module to
        find the corresponding ESA defined Sentinel-2 product tiles that the
        ROI overlaps.

        Note
        ----
        coordlist must be in the format [(lon1, lat1), (lon2, lat2), ... ]
        First and last co-ordinates given in coordlist must be the same to
        complete the described area.

        Parameters
        ----------
        coordlist : list
            List containing the coordinates describing the boundary of the
            region of interest.

        Returns
        -------
        None

        """

        if type(coordlist) is str:
            self.coords_from_file(coordlist)
            return

        if type(coordlist) is not list or len(coordlist[0]) is not 2:
            print(self.coordinates.__doc__)
            raise TypeError("You must follow the coordlist format "
                            "requirements.")

        if len(coordlist) is 1:
            raise NotImplementedError('This script does not currently support '
                                      'queries for single coordinates, please '
                                      'provide a list of coordinates '
                                      'describing your area of interest.')

        if (coordlist[0][0] != coordlist[-1][0] or coordlist[0][1] !=
            coordlist[-1][1]): # noqa
            raise ValueError("The first and last co-ordinates given "
                             "must be the same.")

        # define Region Of Interest as a shapely object
        ROI = Polygon(coordlist)

        self.coordinates = ROI.exterior.coords
        self.ROI = ROI

    def product_details(self,
                        proclevel=False,
                        producttype=False,
                        mode=False,
                        polarisation=False,
                        orbitdirection=False,
                        resolution=False,
                        cloudcoverlimit=False):
        """Sets product search the satellite type and details.

        Note
        ----
        Some combinations will always produce no results, eg. GRD products do
        note have 'HH' polarisations (as of 25th July 2018) and so queries
        using GRD and HH with return 0 results.
        If in doubt, broaden the parameters and always consult the ESA docs.
        See https://sentinel.esa.int/web/sentinel/user-guides for reference.

        Parameters
        ----------
        proclevel : str, optional
            Current S1 processing levels supported: 'L0', 'L1', 'L2', 'ALL'
            Current S2 processing levels supported: 'L1C', 'L2A', 'BEST', 'ALL'
            'BEST' searches for the highest level processed product from
            available Sentinel-2 data for the given co-ordinates.
        producttype : str, optional
            Current product type supported for S1: 'RAW', 'SLC', 'GRD', 'OCN'
            Not supported for S2
        mode : str, optional
            Current S1 modes identifiers supported: 'SM', 'IW', 'EW', 'WV'
            Not supported for S2
        polarisation : str, optional
            Current S1 polarisations supported: 'HH', 'VV', 'HV', 'VH',
            'HH HV', 'VV VH'
            Not supported for S2
        orbitdirection : str, optional
            S1 parameter for orbit direction: 'Ascending' or 'Descending'
            Not supported for S2
        resolution : str, optional
            Current S1 resolutions supported: F, H, M
            Not supported for S2
        cloudcoverlimit : int, optional
            Not supported for S1
            Integer threshold, products with percentage cloud cover higher than
            the threshold with be excluded from the query results.

        """

        sat = self.satellite

        if sat is 'S2':
            if (producttype or mode or resolution or polarisation or
                    orbitdirection):
                print(self.product_details.__doc__)
                raise ValueError(" Product type, mode, polarisation, "
                                 "resolution, orbitdirection are only"
                                 " for S1 products.")
            if proclevel not in ['L1C', 'L2A', 'BEST', 'ALL']:
                print(self.product_details.__doc__)
                raise ValueError
            if type(cloudcoverlimit) is int:
                self.cloudcoverlimit = cloudcoverlimit

        if sat is 'S1':
            if proclevel and proclevel not in ['L0', 'L1', 'L2', 'ALL']:
                print(self.product_details.__doc__)
                raise ValueError
            if producttype and producttype not in ['RAW', 'SLC', 'GRD', 'OCN']:
                print(self.product_details.__doc__)
                raise ValueError
            if mode and mode not in ['SM', 'IW', 'EW', 'WV']:
                print(self.product_details.__doc__)
                raise ValueError
            if polarisation and polarisation not in ['HH', 'VV', 'HV', 'VH',
                                                     'HH HV', 'VV VH']:
                print(self.product_details.__doc__)
                raise ValueError
            if orbitdirection and (orbitdirection
                                   not in ['Ascending', 'Descending']):
                print(self.product_details.__doc__)
                raise ValueError
            if resolution and resolution not in ['F', 'H', 'M']:
                print(self.product_details.__doc__)
                raise ValueError
            if cloudcoverlimit:
                print(self.product_details.__doc__)
                raise ValueError('Cloud cover limit is only for S2 products.')

        self.satellite = sat
        self.proclevel = proclevel
        # detail keys preformatted to their respective User Guide search terms
        self.details = {'producttype:': producttype,
                        'sensoroperationalmode:': mode,
                        'polarisationmode:': polarisation,
                        'resolution:': resolution,
                        'orbitdirection:': orbitdirection}


class CopernicusHubConnection:
    """Handles queries and product downloads to and from the ESA SciHub.

    Attributes
    ----------
    username : str
        The user's ESA account username.
    password : str
        The user's ESA account password.

    """

    def __init__(self):

        self.username = ESA_USERNAME
        self.password = ESA_PASSWORD

    def raw_query(self, query):
        """Queries the ESA SciHub with a pre-formatted query.

        Note
        ----
        This is mainly used by the gs_localmanager module and should not
        generally be used for queries. Use the submit_query method instead.

        Parameters
        ----------
        query : str
            Pre-forammted search query string.

        Returns
        -------
        total_results : int
            Number of results returned from the query
        product_list : dict
            Contains all the products returned from the query, keyed by their
            product UUID

        """

        url = 'https://scihub.copernicus.eu/dhus/search?q=' + query
        r = requests.get(url, auth=(self.username, self.password))
        response = ET.fromstring(r.content)  # parse to XML

        total_results, product_list = self._handle_response(response, False)

        return total_results, product_list

    def submit_query(self, parameters):
        """Formats and submits a query to the ESA scihub via requests.

        Note
        ----
        The working of this function relies heavily on the format of the XML
        returned by the ESA remaining constant.
        Returns the number of results and a dict contain the results UUIDs and
        information.

        Parameters
        ----------
        parameters : :obj:`Query`

        Returns
        -------
        num_results : int
            Number of results returned from the query
        product_list : dict
            Contains all the products returned from the query, keyed by their
            product UUID

        """

        if not parameters.dates:
            raise RuntimeError(" Please set the date in the product search"
                               " parameters before submitting a query.")
        if not parameters.coordinates:
            raise RuntimeError(" Please set the co-ordinates of the product"
                               " search parameters before submitting a query.")

        start = 0
        rows = 100
        query = self._build_query(parameters, start=start, rows=rows)
        response = None

        procfilter = False
        # Filter S2 L1C products out if L2A over same area exists
        if parameters.proclevel is 'BEST':
            procfilter = True

        def send_query(query):
            r = requests.get('https://scihub.copernicus.eu/dhus/search',
                             params=query,
                             auth=(self.username, self.password))
            nonlocal response
            response = ET.fromstring(r.content)  # parse to XML

        def get_index_results():
                # get the current results index and results per page
            index = int(response.findall('{http://a9.com/-/spec/opensearch/'
                                         '1.1/}startIndex')[0].text)
            results_per_page = int(response.findall('{http://a9.com/-/spec/'
                                                    'opensearch/1.1/}items'
                                                    'PerPage')[0].text)
            return index + results_per_page

        # send first query to the server, will return default results 1 to 100
        print("Querying the ESA SciHub using given search parameters.")
        send_query(query)
        # returns the products from the first query
        num_results, product_list = self._handle_response(response,
                                                          procfilter)
        # gets the total amount of products that match the search query
        # this number is used to define how far we need to iterate through
        # the search pages (ESA enforces a limit of 100 results per page)
        total_results = int(response.findall('{http://a9.com/-/spec/opensearch'
                                             '/1.1/}totalResults')[0].text)

        # while the number of results processed is less than the current page
        # index + the amount of results on the page
        while total_results > get_index_results():
            # get the next 100 results
            start = start + 100
            # rebuild the query to ask for the next 100 results
            query['start'] = start
            # send the rebuild query
            send_query(query)
            results, products = self._handle_response(response,
                                                      procfilter)
            num_results = num_results + results
            product_list = {**product_list, **products}
            print("Paging through results, at index {0} / {1}"
                  "".format(start, total_results))

        if procfilter:
            print("Processing filter discarded {0} sub-optimally processed "
                  "products".format(total_results - num_results))

        print("No. Products returned: {0}".format(num_results))

        return num_results, product_list

    def download_quicklooks(self, productlist, downloadpath=QUICKLOOKS_PATH):
        """Downloads the quicklooks of  products to a specified directory.

        Note
        ----
        If no quicklook is available for a product, HTML status code
        500 is returned. In this case, the ESA placeholder 'No Quicklook'
        image is downloaded.

        Parameters
        ----------
        product_list : dict
            Contains all the products whose quicklooks will be downlaoded,
            keyed by their product UUID
        downloadpath : str, optional
            Path to the directory where the quicklooks should be downloaded.
            Default is the QUICKLOOKS_PATH default from gs_config.

        Returns
        -------
        None

        """

        quicklooks_path = pathlib.Path(downloadpath)
        quicklooks_path.mkdir(exist_ok=True)
        existing_quicklooks = [x for x in list(quicklooks_path.glob('*'))]

        print("Downloading quicklooks to {0}".format(QUICKLOOKS_PATH))

        for uuid, product in productlist.items():
            if product['identifier'] in existing_quicklooks:
                pass  # skip if already downloaded
            url = product['quicklookdownload']
            response = requests.get(url,
                                    auth=(self.username, self.password),
                                    stream=True)
            filename = os.path.join(downloadpath, product['identifier'])+'.jp2'
            if response.status_code == 500:  # If no quicklook available
                url = ('https://scihub.copernicus.eu/dhus/images/'
                       'bigplaceholder.png')
                response = requests.get(url, stream=True)
            with open(filename, 'wb') as handle:
                for chunk in response.iter_content(chunk_size=512):
                    if chunk:  # filter out keep-alive new chunks
                        handle.write(chunk)

    def download_products(self, products, verify=False):
        """Downloads the products product_list to the downloadpath directory.

        Parameters
        ----------
        productlist : dict
            Contains all the product returned from the query, keyed by their
            product UUID
        verify : bool
            If true, downloads are checked using MD5 checksum

        Returns
        -------
        None
        """

        # Copy the dict so that it doesnt get cleared and can still be used in
        # a parent script
        productlist = products.copy()
        downloadpath = DATA_PATH  # imported from gs_config
        product_inventory = gs_localmanager.get_product_inventory()
        already_downloaded = list(product_inventory.keys())

        total_products = len(productlist)
        i = 1  # used for product count

        for uuid, product in productlist.copy().items():
            if uuid in already_downloaded:  # skip files already downloaded
                print("Product {0} with UUID {1} is already present in the"
                      " download directory - skipping.".format(
                          product['filename'],
                          uuid))
                productlist.pop(uuid, None)
                i = i + 1
                continue

            print("Downloading product {0} / {1}.".format(i, total_products))
            filename = self._download_single_product(uuid,
                                                     downloadpath,
                                                     verify)
            zip_ref = zipfile.ZipFile(filename, 'r')
            extract_to = downloadpath
            print("Extracting the .zip file.")
            zip_ref.extractall(extract_to)
            zip_ref.close()
            # remove leftover .zip file
            pathlib.Path(filename).unlink()
            # add products iteratively so that if process crashes at any point,
            # earlier products downloaded in the chain will be present in the
            # inventory.
            gs_localmanager.add_new_products({uuid: product})
            i = i + 1

    def _download_single_product(self,
                                 uuid: str,
                                 downloadpath: str,
                                 verify: bool = False):
        """
        Downloads a single product from its uuid and verifies the download
        using MD5 checksum if verify = True.
        """

        downloadurl = ("https://scihub.copernicus.eu/dhus/odata/v1/"
                       "Products('{0}')/$value").format(uuid)
        response = requests.get(downloadurl,
                                auth=(self.username, self.password),
                                stream=True)
        filename = response.headers.get('content-disposition')
        filename = filename.split('"')[1]
        downloadpath = pathlib.Path(downloadpath)
        filepath = pathlib.Path.joinpath(downloadpath, filename)
        if response.status_code == 500:
            raise FileNotFoundError('The product with UUID {0} could not be'
                                    'found.'.format(uuid))
        try:
            with filepath.open('wb') as handle:
                filelength = int(response.headers.get('content-length'))
                print('Downloading product: \n {0}  \nwith UUID:'
                      '{1}'.format(filename,
                                   uuid))
                for chunk in progress.bar(
                        response.iter_content(chunk_size=1024),
                        expected_size=(filelength/1024) + 1):
                    if chunk:  # filter out keep-alive new chunks
                        handle.write(chunk)
                        handle.flush()
        except KeyboardInterrupt:
            filepath.unlink()
            exit()

        # check the download was successful using MD5 Checksum
        if verify:
            checksumurl = ("https://scihub.copernicus.eu/dhus/odata/v1/"
                           "Products('{0}')/Checksum/Value/$value"
                           ).format(uuid)
            response = requests.get(checksumurl,
                                    auth=(self.username, self.password))
            # ESA supplied MD5 checksum for file
            checksum = response.content.decode('utf8').lower()
            md5hash = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5hash.update(chunk)
            filesum = md5hash.hexdigest()
            if checksum != filesum:
                raise ChecksumError(('The following product download failed'
                                     ' verification: \n {0} \n UUID : {1}'
                                     '').format(filename, uuid))
        return filepath

    def _handle_response(self,
                         response: ET.Element,
                         procfilter: bool):
        """
        Handles the query response using the xml library. Formats the xml data
        into usable dict format and also filters for highest processing level
        of each product if procfilter = True.
        """

        entries = response.findall('{http://www.w3.org/2005/Atom}entry')

        # convert from XML to dictionary format
        productlist = {}

        for entry in entries:
            product = {}
            for field in entry:
                if field.get('href') is not None:
                    if field.get('href').endswith("('Quicklook')/$value"):
                        product['quicklookdownload'] = field.get('href')
                        continue
                    if field.get('href').endswith('$value'):  # download links
                        product['downloadlink'] = field.get('href')
                if field.get('name') == 'uuid':
                    uuid = field.text
                    product['origin'] = field.text
                    continue
                if field.get('name') != 'None':  # contain redudancies
                    product[field.get('name')] = field.text
            product['userprocessed'] = False
            productlist[uuid] = product

        # filter out S2 L1C products if equivalent L2A exists
        def proc_fail_warning(id1, id2):
            message = ("Failed to resolve a processling level"
                       " filter beween products {0} and {1}. Both"
                       " products have been retained in the"
                       " search results.")
            message = message.format(id1, id2)
            warnings.warn(message)
        if procfilter:
            # removes any lesser processed products when a higher processed
            # product is present.
            for uuid in list(productlist.keys()):
                try:  # handles case where a uuid has already been removed but
                    product = productlist[uuid]  # key is still present
                except KeyError:
                    continue
                # find matching tile and times
                tile = product['tileid']
                sensingtime = product['beginposition']
                otherproducts = productlist.copy()
                otherproducts.pop(uuid, None)
                for uuid2, product2 in otherproducts.items():
                    tile2 = product2['tileid']
                    sensingtime2 = product2['beginposition']

                    if tile == tile2 and sensingtime == sensingtime2:
                        if product['processinglevel'] == 'Level-1C':
                            if 'Level-2A' in product2['processinglevel']:
                                productlist.pop(uuid, None)
                            else:
                                proc_fail_warning(product['identifier'],
                                                  product2['identifier'])
                        if product2['processinglevel'] == 'Level-1C':
                            if 'Level-2A' in product['processinglevel']:
                                productlist.pop(uuid2, None)
                            else:
                                proc_fail_warning(product['identifier'],
                                                  product2['identifier'])
        totalresults = len(productlist)

        return totalresults, productlist

    def _build_query(self,
                     parameters: Query,
                     start: int = 0,
                     rows: int = 100):
        """
        Builds the query for use with the requests module.
        Query syntax from:
        https://scihub.copernicus.eu/userguide/5APIsAndBatchScripting
        https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/3FullTextSearch
        """

        query = {'q': '*'}
        join = ' AND '

        def term_join(field, value):
            query['q'] = query['q'] + join + field + str(value)

        if parameters.satellite:
            field = 'platformname:'
            if parameters.satellite is 'S1':
                value = 'Sentinel-1'
            if parameters.satellite is 'S2':
                value = 'Sentinel-2'
            term_join(field, value)

        # Formatting the dates query

        start_date = str(parameters.dates[0])+'T00:00:00.000Z'
        # set the end date to one day later
        end_date = (str(parameters.dates[0] + datetime.timedelta(days=1))
                    + 'T00:00:00.000Z')
        # if an end date set by the user, overwrite
        if parameters.dates[1]:
            end_date = (str(parameters.dates[1] + datetime.timedelta(days=1))
                        + 'T00:00:00.000Z')

        field = 'beginposition:'
        value = '[' + start_date + ' TO ' + end_date + ']'
        term_join(field, value)

        # Formatting the co-ordinates intersect query

        value = '"intersects('
        value = value + parameters.ROI.wkt  # add the ROI WKT format to query
        value = value + ')"'
        field = 'footprint:'
        term_join(field, value)

        # Adding other product details to the query

        for key in parameters.details:
            if parameters.details[key]:
                term_join(key, parameters.details[key])

        # If cloud cover limit is set for S2 products
        if hasattr(parameters, 'cloudcoverlimit'):
            field = 'cloudcoverpercentage:'
            value = '[0 TO {0}]'.format(parameters.cloudcoverlimit)
            term_join(field, value)

        # If searching for S1 products, can directly add required proc level
        # to query term in short hand (see User Guide)

        if parameters.satellite is 'S1':
            if parameters.proclevel and parameters.proclevel != 'ALL':
                term_join('', parameters.proclevel)
        if parameters.satellite is 'S2':
            field = 'producttype:'
            if parameters.proclevel == 'L1C':
                term_join(field, 'S2MSI1C')
            if parameters.proclevel == 'L2A':
                term_join(field, 'S2MSI2A')

        # Add the start and end row limits for the query
        query['start'] = str(start)
        query['rows'] = str(rows)

        return query


def filter_overlaps(product_list, ROI, external_list=False):
    """Filters out any overlapping products

    If the ROI coordinates are completely encompassed by two products and
    the sensing time for both products is the same, the products will have
    identical data in the overlapping regions. Thus one of them can be removed
    from the downloads required.

    Parameters
    ----------
    product_list : dict
        Contains all the products returned from the query, keyed by their
        product UUID
    ROI : :obj:`shapely.geometry.Polygon`
    external_list : dict
        A list of products provided that represents the products already
        present in the inventory. Prevents filtering from removing one product
        over another when the first is already present in the inventory.

    """

    def extract_time(time_string):
        # creates a datetime object from the given time string
        sense_year = int(time_string[0:4])
        sense_month = int(time_string[5:7])
        sense_day = int(time_string[8:10])
        sense_hour = int(time_string[11:13])
        sense_minute = int(time_string[14:16])
        sense_second = int(time_string[17:19])
        time = datetime.datetime(sense_year,
                                 sense_month,
                                 sense_day,
                                 sense_hour,
                                 sense_minute,
                                 sense_second)
        return time

    encompassing_products = []

    num_products_passed = len(product_list)

    for uuid, product in product_list.copy().items():
        # format the footprint string for use with pyshp
        footprint = loads(product['footprint'])  # load in via shapely
        # if ROI fully encompassed by a product
        if ROI.within(footprint):
            encompassing_products.append(uuid)
        if external_list:
            if uuid in external_list:
                # if encompassing product already in given list
                # then remove it. This stops the edge case where one
                # encompassing product gets preferred over another even though
                # the second is already downloaded (ie. present in the external
                # list). This would cause duplicate data in the final batch
                # list.
                product_list.pop(uuid, None)

    # filter out duplicates
    product_list_copy = product_list.copy()
    for uuid in encompassing_products:
        try:
            product = product_list[uuid]
        except KeyError:  # product already removed
            continue
        if product['platformname'].endswith('2'):

            proclevel = product['processinglevel']
            sensing_time = product['beginposition']

            for uuid2, product2 in product_list_copy.items():
                if (uuid is uuid2 or product2['platformname'] !=
                  product['platformname']): # noqa
                    continue
                if (product2['processinglevel'] == proclevel and
                  product2['beginposition'] == sensing_time): # noqa
                    product_list.pop(uuid2, None)  # removes overlapping tile
                    break

        if product['platformname'].endswith('1'):

            prodtype = product['producttype']
            polarisation = product['polarisationmode']
            sensing_begin = product['beginposition']
            sensing_begin = extract_time(sensing_begin)
            sensing_end = product['endposition']
            sensing_end = extract_time(sensing_end)

            for uuid2, product2 in product_list_copy.items():
                if (uuid is uuid2 or product2['platformname'] !=
                  product['platformname']): # noqa
                    continue
                sensing_begin_2 = product2['beginposition']
                sensing_begin_2 = extract_time(sensing_begin_2)
                # If second product has sensing time before the end of first
                # product, that indicates data overlap
                if (sensing_begin < sensing_begin_2 < sensing_end):
                    if (product2['producttype'] == prodtype and
                      product2['polarisationmode'] == polarisation): # noqa
                        product_list.pop(uuid2, None)
                        break

    products_removed = num_products_passed - len(product_list)

    print("filter_overlaps : {0} product(s) filtered"
          " out.".format(products_removed))

    return product_list


class ChecksumError(Exception):
    """Checksum Exception for when checksums do not match in downloading."""
    pass
