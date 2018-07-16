"""
Submodule for handling polygon intersection tests.

NOTE: This is for testing longitude and latitude polygons
against the sentinel 2 tiling grid. It may be unstable with
very large polygons (>150 grid squares) due to the optimisation.

@author: Joe Fennell
"""

from shapely.geometry import Polygon
import numpy as np
from pathlib import Path
cwd = str(Path(__file__).resolve().parent)

class grid_finder(object):
    """ Class for processing multiple grid lookup requests
    By default, this loads the lookup arrays into memory prior
    to calling a lookup request.
    """
    
    def __init__(self,LL_path=cwd+'/s2_tiling_grid_np_ll.npy',
                 names_path=cwd+'/s2_tiling_grid_np_names.npy'):
        
        # define arrays
        self.LLs, self.names = _get_lookup_arrays(LL_path,names_path)
        # do 360 conversion now
        # transform
        self.LLs[:,::2] = _to_360(self.LLs[:,::2])
    
    def request(self,X):
        """
        Returns a list of grid squares intersecting X when
        x is a 1D array or list in format [Lon_1,Lat_1,Lon_2,Lat_2,...]
        """
        # Convert to 360 deg system WRT greenwich meridian at 0
        X = np.array(X)
        x360 = _to_360(X[::2])

        # get the rotation vector for a 1D polar rotation to approximately
        # centre the polygon at 180deg
        rot = _get_rotation(x360)

        # apply the longitude rotation
        X[::2] = _rotate(x360,rot)

        # lets make a copy of the tiling array
        Y = np.copy(self.LLs)

        

        # rotate by same vector
        yrot = _rotate(Y[:,::2],rot)
        Y[:,::2] = yrot

        Y_sub, names_sub = _remove_distant(X,Y,self.names)
        return _get_intersects(X,Y_sub,names_sub)
    
def WKT_to_list(wkt_multipolygon):
    """ 
    takes a Well Known Text string [i.e. 
    'POLYGON(((lon_1 lat_1,lon_2 lat_2, ... )))'] and returns a
    list of coordinates in format [lon_1, lat1, lon2, lat2, ... ]
    
    """
    pairs = wkt_multipolygon.split('(')[-1].split(')')[0].split(',')
    out_list = []
    for x in pairs:
        x_ = x.split()
        # lon lat order
        out_list.append(float(x_[0]))
        out_list.append(float(x_[1]))
    return out_list

# private functions
def _get_lookup_arrays(LL_path=cwd+'/s2_tiling_grid_np_ll.npy',
                      names_path=cwd+'/s2_tiling_grid_np_names.npy'):
    """ Returns the array format grid polygons and names arrays
    
    """
    # The data are stored as a numpy array as this is the primary
    # format for use in 
    LLs = np.load(LL_path)
    names = np.load(names_path)
    
    return LLs,names

def _array_to_shapely(array):
    """converts array to coordinate lists (lon then lat)"""
    if len(array.shape) == 2:
        shapes = []
        for i in range(array.shape[0]):
            coords = []
            for x,y in zip(array[i,::2],array[i,1::2]):
                coords.append((x,y))
            shapes.append(Polygon(coords))
        return shapes
    elif len(array.shape) == 1:
        coords = []
        for x,y in zip(array[::2],array[1::2]):
            coords.append((x,y))
        return Polygon(coords)

# conversion to 360
def _to_360(X):
    """
    converts negative deg vals to 180 > val > 360
    """
    X[X<0] = X[X<0]+360
    return X

def _get_rotation(X):
    """
    gets rotation vector (difference from 180)
    """
    return np.abs(X.max()-180)

def _rotate(X, rot):
    """
    applies rotation vector to array
    """
    return (X + np.atleast_2d(rot).T) % 360

def _remove_distant(X,Y,names,lat_thresh=5,lon_thresh=10):
    """ Excludes values beyond a threshold for testing
    set the thresholds conservatively as there are no checks
    for areas of the test polygon that do not have a grid square
    """
    
    # lat boundaries
    xmin = X[1::2].min()
    xmax = X[1::2].max()
    
    # subset poly array
    Y2 = Y[np.all((
        Y[:,0]<(180+lon_thresh),
        Y[:,0]>(180-lon_thresh),
        Y[:,1]>(xmin-lat_thresh),
        Y[:,1]<(xmax+lat_thresh)),axis=0
    ),:]
    
    # subset names array with same rules
    names2 = names[np.all((
        Y[:,0]<(180+lon_thresh),
        Y[:,0]>(180-lon_thresh),
        Y[:,1]>(xmin-lat_thresh),
        Y[:,1]<(xmax+lat_thresh)),axis=0
    )]
    
    return Y2,names2

def _get_intersects(X,Y,names):
    """
    Calculates all intersecting grid squares for polygon
    """
    X_shp = _array_to_shapely(X)
    squares = _array_to_shapely(Y)
    intersects = []
    # iterate all squares in sub_array
    for square,name in zip(squares,names):
        if square.intersects(X_shp):
            intersects.append(name)           
    return intersects


if __name__ == "__main__":
    
    # test script
    
    lookup = gs_gridtest.grid_finder()

    # pakistan test polygon
    X = [70.07080078125,
    33.96158628979907,
    68.31298828125,
    30.80791068136646,
    71.3671875,
    28.285033294640684,
    74.15771484375,
    29.38217507514529,
    75.12451171875,
    32.175612478499325,
    72.83935546875,
    33.87041555094183,
    70.07080078125,
    33.96158628979907]

    pakistan = lookup.request(X)

    print('The polygon covers {} squares, including {}, {}, {},...'.format(
        len(pakistan),
        pakistan[0],
        pakistan[1],
        pakistan[2]
    ))
