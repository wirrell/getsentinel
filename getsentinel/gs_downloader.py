"""
Script to locate and auto-download products from Copernicus Open Access Hub
which contains ESA Sentinel Satellite products. https://scihub.copernicus.eu/

TODO:
    Implemented load in of ROI coordinates from geojson files.
    Speak with Joe about issue with gs_gridtest.grid_under.request method which
    returns many tiles when passed the boundary coordinates of a singe S2 tile.
    Speak with Joe about possibly changing input format of the above method to
    ((lon, lat), (lon, lat), ... ) instead of (lon1, lat1, lon2, lat2, ... ).
    Investigate use of shapely files to store coords in params, could make it
    easier to pass WKT request for ROI to server.

George Worrall - University of Manchester 2018
"""

import datetime
import xml.etree.ElementTree as ET
import warnings
import hashlib
import pathlib
import zipfile
import requests
from clint.textui import progress
from convertbng.util import convert_lonlat
import shapefile
from shapely.geometry import MultiPoint, Polygon
from shapely.wkt import loads
from . import gs_localmanager
from . import gs_gridtest
from .gs_config import DATA_PATH, QUICKLOOKS_PATH, ESA_USERNAME, ESA_PASSWORD


class ProductQueryParams:

    def __init__(self):

        self.dates = False
        self.coords = False

    def acquisition_date_range(self,
                               acqstart: datetime.date,
                               acqend=False):
        """
        Sets the product search acquisition date range.

        Note: This is used to specify the Sensing Start Time search criteria.
              If no end date is specific, the 24 hour period for the given
              start date is used. Any specified end date is considered
              inclusive.
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

        self.dates = [acqstart, acqend]

    def coords_from_file(self,
                         filepath: str,
                         filetype: str,
                         coordsystem: str = 'WGS'):

        """
        Loads in the coordinates of a Region Of Interest (ROI) from a shape
        file or geojson file. Uses shapely module to get a polygon which
        encompasses all of the shapes containined within the shape file.
        Suports WGS87 and BNG coordinate formats.
        """

        # TODO: Implement reading in of coords from geojson files.

        if filetype != '.shp':
            raise NotImplementedError('Currently only .shp files are'
                                      'supported.')

        if coordsystem not in ['WGS', 'BNG']:
            raise NotImplementedError('Currently only supports WGS and BNG'
                                      'format.')

        lon_coords = []
        lat_coords = []
        shp = shapefile.Reader(filepath)
        for shape in shp.shapes():  # extract all points from all shapes
            for point in shape.points:  # in the file
                lon_coords.append(point[0])
                lat_coords.append(point[1])
        if coordsystem == 'BNG':  # convert to WGS
            wgs_list = convert_lonlat(lon_coords, lat_coords)
            lon_coords = wgs_list[0]
            lat_coords = wgs_list[1]

        coords = list(zip(lon_coords, lat_coords))

        m = MultiPoint(coords)  # imported from shapely module
        extents = m.convex_hull  # gets small polygon that encomps all points

        coords = list(extents.exterior.coords)

        self.coordinates(coords)

    def coordinates(self, coordlist: list):

        """
        Converts the given co-ordinates lists to an MGRS 100km Grid Square
        ID. If the co-ordinates traverse square boundaries, all relevant IDs
        are saved. Co-ordinates are also stored for later retreived product
        area coverage checking.

        coordlist must be in the format [(lon1, lat1), (lon2, lat2), ... ]
        First and last co-ordinates given in coordlist must be the same to
        complete the described area.
        """

        if type(coordlist) is not list or len(coordlist[0]) is not 2:
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

        finder = gs_gridtest.grid_finder()
        coords = gs_gridtest.WKT_to_list(ROI.wkt)
        tile_list = finder.request(coords)

        self.tiles = tile_list
        self.coords = coords
        self.ROI = ROI

    def product_details(self, sat: str,
                        proclevel=False,
                        producttype=False,
                        mode=False,
                        polarisation=False,
                        resolution=False,
                        cloudcoverlimit=False):

        """
        Sets product search the satellite type.
        Current satellites supported: S1, S2.
        Current product type supported for S1: RAW, SLC, GRD, OCN
        Current S1 modes identifiers supported: SM, IW, EW, WV
        Current S1 resolutions supported: F, H, M
        Current S1 polarisations supported: HH, VV, HV, VH, HH HV, VV VH
        Current S1 processing levels supported: L0, L1, L2, ALL
        Current S2 processing levels supported: L1C, L2A, BEST, ALL
        Cloud cover limit: integer threshold above which S2 products
        which higher than threshold cloud coverage will be excluded from the
        search.

        Note: BEST searches for the highest level processed product from
        available Sentinel-2 data for the given co-ordinates.

        Note: Some combinations will always produce no results, eg. OCN
        products do not have resolutions options and so an SLC type search with
        parameters will return 0 results.
        If in doubt, broaden the parameters and always consult the docs.

        See https://sentinel.esa.int/web/sentinel/user-guides for reference.

        """

        if sat not in ['S1', 'S2']:
            raise ValueError(" Only Sentinel-1 (use 'S1') and Sentinel-2 (use"
                             " 'S2') products are currently supported.")

        if sat is 'S2':
            if producttype or mode or resolution or polarisation:
                print(self.product_details.__doc__)
                raise ValueError(" Product type, mode, polarisation, "
                                 "resolution are only for S1 products.")
            if proclevel not in ['L1C', 'L2A', 'BEST', 'ALL']:
                print(self.product_details.__doc__)
                raise ValueError
            if cloudcoverlimit:
                self.cloudlimit = cloudcoverlimit
                if type(cloudcoverlimit) is not int:
                    print(self.product_details.__doc__)
                    raise ValueError

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
                        'resolution:': resolution}


class CopernicusHubConnection:

    """
    Class holder for ESA username and password which hosts query and download
    methods that interact directly with the ESA Copernicus SciHub.
    """

    def __init__(self):

        self.username = ESA_USERNAME
        self.password = ESA_PASSWORD

    def raw_query(self, query):

        """
        Handles submission of a raw formatted query. Used by the
        gs_localmanager to look up the product details for products manually
        added to the download directory.
        """

        url = 'https://scihub.copernicus.eu/dhus/search?q=' + query
        r = requests.get(url, auth=(self.username, self.password))
        response = ET.fromstring(r.content)  # parse to XML

        total_results, product_list = self._handle_response(response, False)

        return total_results, product_list

    def submit_query(self, parameters: ProductQueryParams):

        """
        Formats and submits a query to the ESA scihub via the requests library.
        Returns the number of results and a dict contain the results UUIDs and
        information.
        """

        if not parameters.dates:
            raise RuntimeError(" Please set the date in the product search"
                               " parameters before submitting a query.")
        if not parameters.coords:
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

    def download_quicklooks(self,
                            productlist: dict,
                            downloadpath: str = QUICKLOOKS_PATH):

        """
        Downloads the quicklooks of the retrieved products to a specified
        directory for the user to inspect manually before downloading the
        full product list, if they so wish.

        Note: If no quicklook is available for a product, HTML status code
        500 is returned. In this case, the ESA placeholder 'No Quicklook'
        image is downloaded.
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
            filename = downloadpath + product['identifier']
            if response.status_code == 500:  # If no quicklook available
                url = ('https://scihub.copernicus.eu/dhus/images/'
                       'bigplaceholder.png')
                response = requests.get(url, stream=True)
            with open(filename, 'wb') as handle:
                for chunk in response.iter_content(chunk_size=512):
                    if chunk:  # filter out keep-alive new chunks
                        handle.write(chunk)

    def download_products(self,
                          productlist: dict,
                          downloadpath: str = DATA_PATH,
                          verify: bool = False):

        """
        Downloads the products provided in the product list and verifies all
        downloads using MD5 checksum if verify = True.
        """

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
                continue

            print("Downloading product {0} / {1}.".format(i, total_products))
            filename = self._download_single_product(uuid,
                                                     downloadpath,
                                                     verify)
            zip_ref = zipfile.ZipFile(filename, 'r')
            extract_to = downloadpath
            zip_ref.extractall(extract_to)
            zip_ref.close()

            i = i + 1

        data_path = pathlib.Path(DATA_PATH)
        # collect all the leftover .zip files
        zip_files = [x for x in list(data_path.glob('*.zip'))]
        for zip_file in zip_files:
            zip_file.unlink()

        gs_localmanager.add_new_products(productlist)

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
        filepath = downloadpath + filename
        if response.status_code == 500:
            raise FileNotFoundError('The product with UUID {0} could not be'
                                    'found.'.format(uuid))
        with open(filepath, 'wb') as handle:
            filelength = int(response.headers.get('content-length'))
            print('Downloading product: \n {0}  \nwith UUID:'
                  '{1}'.format(filename,
                               uuid))
            for chunk in progress.bar(response.iter_content(chunk_size=1024),
                                      expected_size=(filelength/1024) + 1):
                if chunk:  # filter out keep-alive new chunks
                    handle.write(chunk)

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
            # TODO: Implement 'utmzone' info
            product['userprocessed'] = False
            if 'tileid' not in product:  # get S1 prod. corresponding S2 tiles
                finder = gs_gridtest.grid_finder()
                coord_list = gs_gridtest.WKT_to_list(product['footprint'])
                # returns list of all S2 tiles the product intersects
                # and the majority tile in format
                # ([tile1, tile2, ... ], maj_tile)
                product['tileid'] = finder.request(coord_list)
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
                            if product2['processinglevel'] == 'Level-2A':
                                productlist.pop(uuid, None)
                            else:
                                proc_fail_warning(product['identifier'],
                                                  product2['identifier'])
                        if product2['processinglevel'] == 'Level-1C':
                            if product['processinglevel'] == 'Level-2A':
                                productlist.pop(uuid2, None)
                            else:
                                proc_fail_warning(product['identifier'],
                                                  product2['identifier'])
        totalresults = len(productlist)

        return totalresults, productlist

    def _build_query(self,
                     parameters: ProductQueryParams,
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
        if hasattr(parameters, 'cloudlimit'):
            field = 'cloudcoverpercentage:'
            value = '[0 TO {0}]'.format(parameters.cloudlimit)
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


def filter_overlaps(product_list: dict,
                    ROI: Polygon,
                    external_list: dict = False):

    """
    Filters out any overlapping products if the ROI coordinates
    are completely encompassed by one of the products and the sensing time for
    both products is the same. (Products with the same sensing time will have
    identical data in the overlapping regions.)
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

    return product_list


class ChecksumError(Exception):
    pass


if __name__ == "__main__":

    # get ESA login info

    download_path = DATA_PATH
    quicklooks_path = QUICKLOOKS_PATH

    # aiming for best S2 test product in coords and time frame
    # as filtered by filter_overlaps function
    # S2A_MSIL2A_20180626T110621_N0208_R137_T30UXC_20180626T120032
    s2_testproduct = ProductQueryParams()
    t = datetime.date(2018, 6, 26)
    s2_testproduct.acquisition_date_range(t)
    # ESA required coordinates to be in (lon, lat) format
    test_coords = [
     [-1.457530077065015, 52.19345388039674],
     [-1.459996965719496, 52.19090717497048],
     [-1.466515166082085, 52.18543304302305],
     [-1.463587991194426, 52.18127295502671],
     [-1.458228587403975, 52.17663695482379],
     [-1.455491238873678, 52.17444814271325],
     [-1.452644611915905, 52.17396223669407],
     [-1.444929550955296, 52.17417824001138],
     [-1.448993345097861, 52.19077295431794],
     [-1.450033434119889, 52.19282940614654],
     [-1.454319601915816, 52.19499959454429],
     [-1.457530077065015, 52.19345388039674]]
    s2_testproduct.coordinates(test_coords)
    s2_testproduct.product_details('S2', 'BEST')

    # Aiming for S1 test products
    # S1A_IW_SLC__1SDV_20180628T061437_20180628T061504_022553_027169_519F
    s1_testproduct = ProductQueryParams()
    s1_testproduct.coords_from_file('test_files/CB7_4SS_grid_1 _combi.shp',
                                    '.shp',
                                    'BNG')

    t = datetime.date(2018, 6, 27)
    t_end = datetime.date(2018, 6, 28)
    s1_testproduct.acquisition_date_range(t, t_end)
    s1_testproduct.product_details('S1', 'L1', 'GRD', 'IW', 'VV VH')
    hub = CopernicusHubConnection()

    # Submit queries to ESA scihub API
    totals2, s2products = hub.submit_query(s2_testproduct)
    totals1, s1products = hub.submit_query(s1_testproduct)
    s2products = filter_overlaps(s2products, s2_testproduct.ROI)
    s1products = filter_overlaps(s1products, s1_testproduct.ROI)
    hub.download_quicklooks(s2products, quicklooks_path)
    hub.download_quicklooks(s1products, quicklooks_path)
    hub.download_products(s2products, download_path, verify=True)
    hub.download_products(s1products, download_path, verify=True)
