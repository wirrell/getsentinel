"""
Script to locate and auto-download products from Copernicus Open Access Hub
which contains ESA Sentinel Satellite products. https://scihub.copernicus.eu/

TODO:
    Implement Sentinel-2 auto download for single products
    Implement Sentinel-1 auto download for single products
    Implement multiple time-frame download of prodcuts for a given area
    Write handling for co-ordinates lists that traverse mulitple MGRS squares
    including sticthing of downloaded products (stitching may not be necessary
    is all Sentinel products have sufficient overlap).
    Implement loading in of co-ordinates directly from parsed shape files.

George Worrall - University of Manchester 2018
"""

import datetime
import mgrs
import requests

class productQueryParams:

    def __init__(self):

        self.dates = False
        self.coords = False

    def acquisitionDateRange(self,
                        acqstart : datetime.date,
                        acqend = False):

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

        self.dates = [acqstart, acqend]



    def coordinates(self, coordlist : list):

        """
        Converts the given co-ordinates lists to an MGRS 100km Grid Square
        ID. If the co-ordinates traverse square boundaries, all relevant IDs
        are saved. Co-ordinates are also stored for later retreived product
        area coverage checking.
        
        coordlist must be in the format [[lat, lon], [lat, lon], ... ]
        First and last co-ordinates given in coordlist must be the same to
        complete the described area.
        """

        #TODO: Implement loading in of co-ordinates from shape file

        if type(coordlist) is not list or type(coordlist[0]) is not list:
            raise TypeError("You must follow the coordlist format "
                            "requirements.")

        if len(coordlist) is 1:
            raise NotImplementedError('This script does not currently support '
                                      'queries for single coordinates, please '
                                      'provide a list of coordinates '
                                      'describing your area of interest.')

        if (coordlist[0][0] != coordlist[-1][0] or coordlist[0][1] !=
            coordlist[-1][1]):
            raise ValueError("The first and last co-ordinates given "
                             "must be the same.")

        tile_list = []
        m = mgrs.MGRS() # converts latitude and longitude to MGRS co-ords

        
        for (lat, lon) in coordlist:
            m_coord = m.toMGRS(lat, lon, MGRSPrecision=1) # 7 digit output
            tile = m_coord[:-2].decode("utf-8") # sliced to 5 digit tile no.
            tile_list.append(tile)

        self.tiles = list(set(tile_list))
        self.coords = coordlist

        #TODO: Implement multi-tile support including stitching of downloaded
        # products (stiching may not be necessary if all products have
        # sufficient overlap).
        if len(self.tiles) is not 1:
            raise NotImplementedError("The given co-ordinates traverse more"
                                      " than one MGRS tile. Multi MGRS tile"
                                      " support has not yet been implemented.")

    def productDetails(self, sat : str,
                       proclevel = False,
                       producttype = False,
                       mode = False,
                       polarisation = False,
                       resolution = False,
                       cloudcoverlimit = False):

        """
        Sets product search the satellite type.
        Current satellites supported: S1, S2.
        Current product type supported for S1: RAW, SLC, GRD, OCN
        Current S1 modes identifiers supported: SM, IW, EW, WV
        Current S1 resolutions supported: F, H, M
        Current S1 polarisations supported: HH, VV, HV, VH, HH HV, VV VH
        Current S1 processing levels supported: L0, L1, L2
        Current S2 processing levels supported: L1C, L2A, BEST
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
                print(self.productDetails.__doc__)
                raise ValueError(" Product type, mode, polarisation, "
                                 "resolution are only for S1 products.")
            if proclevel not in ['L1C', 'L2A', 'BEST']:
                print(self.productDetails.__doc__)
                raise ValueError
            if type(cloudcoverlimit) is not int:
                print(self.productDetails.__doc__)
                raise ValueError
            self.cloudlimit = cloudcoverlimit

        if sat is 'S1':
            if proclevel and proclevel not in ['L0', 'L1', 'L2']:
                print(self.productDetails.__doc__)
                raise ValueError
            if producttype and producttype not in ['RAW', 'SLC', 'GRD', 'OCN']:
                print(self.productDetails.__doc__)
                raise ValueError
            if mode and mode not in ['SM', 'IW', 'EW', 'WV']:
                print(self.productDetails.__doc__)
                raise ValueError
            if polarisation and polarisation not in ['HH', 'VV', 'HV', 'VH',
                                                     'HH HV', 'VV VH']:
                print(self.productDetails.__doc__)
                raise ValueError
            if resolution and resolution not in ['F', 'H', 'M']:
                print(self.productDetails.__doc__)
                raise ValueError
            if cloudcoverlimit:
                print(self.productDetails.__doc__)
                raise ValueError('Cloud cover limit is only for S2 products.')



        self.satellite = sat
        self.proclevel = proclevel
        # detail keys preformatted to their respective User Guide search terms
        self.details = {'producttype:' :producttype,
                        'sensoroperationalmode:' : mode,
                        'polarisationmode:' : polarisation,
                        'resolution:' : resolution}


def submitQuery(parameters : productQueryParams,
                esa_username : str,
                esa_password : str):

    """
    Formats and submits a query to the ESA scihub via the requests module.
    """

    if not parameters.dates:
        raise RuntimeError(" Please set the date in the product search"
                           " parameters before submitting a query.")
    if not parameters.coords:
        raise RuntimeError(" Please set the co-ordinates of the product"
                           " search parameters before submitting a query.")

    query = _buildQuery(parameters)


def _buildQuery(parameters : productQueryParams) -> dict: 

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
                    +'T00:00:00.000Z')
    # if an end date set by the user, overwrite
    if parameters.dates[1]:
        end_date = (str(parameters.dates[1] + datetime.timedelta(days=1))
                        +'T00:00:00.000Z')

    field = 'beginposition:'
    value = '[' + start_date + ' TO ' + end_date + ']'
    term_join(field, value)

    # Formatting the co-ordinates intersect query

    value = '"intersects(POLYGON(('
    for coord in parameters.coords:
        # must switch order of lat, lon to lon, lat as required by polygon
        # format specified in ESA SciHub User Guide
        value = value + str(coord[1]) + ' ' + str(coord[0]) + ','
    value = value[:-1] + ')))"'
    field = 'footprint:'
    term_join(field, value)

    # Adding other product details to the query

    for key in parameters.details:
        if parameters.details[key]:
            term_join(key, parameters.details[key])

    # If searching for S1 products, can directly add required processing level
    # to query term in short hand (see User Guide)

    if parameters.satellite is 'S1':
        if parameters.proclevel:
            term_join('', parameters.proclevel)

    print(query)



        



    
    
    




            


        



if __name__ == "__main__":

    # aiming for S2 test product
    # S2A_MSIL2A_20170102T111442_N0204_R137_T30UXC_20170102T111441
    # via BEST search which will kick back no L2A but one L1C
    s2_testproduct = productQueryParams()
    t = datetime.date(2017, 1, 2)
    s2_testproduct.acquisitionDateRange(t)
    test_coords = [
     [52.19345388039674,-1.457530077065015],
     [52.19090717497048,-1.459996965719496],
     [52.18543304302305,-1.466515166082085],
     [52.18127295502671,-1.463587991194426],
     [52.17663695482379,-1.458228587403975],
     [52.17444814271325,-1.455491238873678],
     [52.17396223669407,-1.452644611915905],
     [52.17417824001138,-1.444929550955296],
     [52.19077295431794,-1.448993345097861],
     [52.19282940614654,-1.450033434119889],
     [52.19499959454429,-1.454319601915816],
     [52.19345388039674,-1.457530077065015]]
    s2_testproduct.coordinates(test_coords)
    s2_testproduct.productDetails('S2', 'BEST', cloudcoverlimit=95)
    print(s2_testproduct.satellite)
    print(s2_testproduct.details)
    # Aiming for S1 test product
    # S1B_IW_SLC__1SDV_20170103T062212_20170103T062239_003680_00650F_B009
    s1_testproduct = productQueryParams()
    s1_testproduct.coordinates(test_coords)
    t_end = datetime.date(2017, 1, 3)
    s1_testproduct.acquisitionDateRange(t, t_end)
    s1_testproduct.productDetails('S1', 'L1', 'SLC', 'IW', 'VV VH') 
    print(s1_testproduct.satellite)
    print(s1_testproduct.details)
    submitQuery(s2_testproduct)
    submitQuery(s1_testproduct)




