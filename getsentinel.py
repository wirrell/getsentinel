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

George Worrall - University of Manchester 2018
"""

import datetime
import mgrs

class productSearch:

    def acquisitionDate(self, acqdate : datetime.date):
        
        """Sets the product search acquisition date. """

        if type(acqdate) is not datetime.date:
            raise TypeError("You must pass a datetime.date object to this "
                            "method.")

        self.date = acqdate

    def coordinates(self, coordlist : list):

        """
        Converts the given co-ordinates lists to an MGRS 100km Grid Square
        ID. If the co-ordinates traverse square boundaries, all relevant IDs
        are saved. Co-ordinates are also stored for later retreived product
        area coverage checking.
        
        coordlist must be in the format [[lat, lon], [lat, lon], ... ]

        """

        if type(coordlist) is not list or type(coordlist[0]) is not list:
            print(self.coordinates.__doc__)
            raise TypeError("You must follow the coordlist format "
                            "requirements.")

        tile_list = []
        m = mgrs.MGRS() # converts latitude and longitude to MGRS co-ords
        
        for (lat, lon) in coordlist:
            m_coord = m.toMGRS(lat, lon, MGRSPrecision=1)
            tile = m_coord[:-2].decode("utf-8")
            tile_list.append(tile)

        self.tiles = list(set(tile_list))

        #TODO: Implement multi-tile support including stitching of downloaded
        # products (stiching may not be necessary if all products have
        # sufficient overlap).
        if len(self.tiles) is not 1:
            raise NotImplementedError("The given co-ordinates traverse more"
                                      " than one MGRS tile. Multi MGRS tile"
                                      " support has not yet been implemented.")

            


        



if __name__ == "__main__":

    testproduct = productSearch()
    t = datetime.date(2017, 1, 2)
    testproduct.acquisitionDate(t)
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
    testproduct.coordinates(test_coords)
    print(testproduct.tiles)



