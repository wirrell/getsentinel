"""getsentinel gs_preprocessor.py

Invokes the sen2cor processor for S2 and gpt for S1 to processed products to a
usable level.

Example
-------
Basic usage example::

    from getsentinel import gs_preprocessor

    for_processing = gs_preprocessor.get_processable_files()

    for uuid, pipeline in inventory.items():
        gs_preprocessor.process(uuid, pipeline)


Todo
----
class for invoking processors
product_entry fields to modify:
Implmenet S3 support
"""

from . import gs_localmanager
from .gs_config import SEN2COR_ROOT_PATH, DATA_PATH, GPT_ROOT_PATH
import xml.etree.ElementTree as ET
import warnings
import os, shutil, subprocess

def get_processable_files(inventory=None, ignore_processed=True):
    """Checks the inventory file for compatible file types which have
    not yet been processed.
    
    Parameters
    ----------
    inventory : dict, optional
        Product inventory containing product info keyed by produt uuid.
        
    Returns
    -------
    out : dict
        Required pipelines 'S2', 'S1_UTM', etc keyed by corresponding product
        uuid.

    """

    # get a product inventory if none supplied.
    # A restricted or prefiltered inventory could be supplied
    # if, for example a certain geographic restriction was needed

    if inventory == None:
        inventory = gs_localmanager.get_product_inventory()

    # apply set logic
    unprocessed_S2L1C = set()
    unprocessed_S2L2A = set()
    unprocessed_S1 = set()
    processed_S2L2A = set()
    processed_S1 = set()

    for uuid,product in inventory.items():
        # check if sentinel 2
        if product['producttype'] == 'S2MSI1C':
            # add all unprocessed S2 L1C
            unprocessed_S2L1C.add(uuid)

        elif product['producttype'] == 'S2MSI2A' and\
        product['userprocessed'] == False:
            unprocessed_S2L2A.add(uuid)
            pass

        elif product['producttype'] == 'S2MSI2A' and\
        product['userprocessed'] == True:
        # strip the -user from the uuid
            processed_S2L2A.add(uuid.split('-user')[0])

        elif product['producttype'] == 'GRD':
            unprocessed_S1.add(uuid)

        elif product['producttype'] == 'GRD_L2':
            processed_S1.add(uuid.split('-user')[0])

        else:
            _prod_warning(uuid)

    # logic testing
    # S2 processing list
    S2_proc_list = list(unprocessed_S2L1C.difference(processed_S2L2A))
    # S1 processing list
    S1_proc_list = list(unprocessed_S1.difference(processed_S1))

    # make output dict

    out = dict()

    for uuid in S2_proc_list:
        out[uuid] = 'S2'

    for uuid in S1_proc_list:
        out[uuid] = 'S1_UTM'

    return out

def process(uuid,pipeline,inventory=None):
    """    Runs the processing operation for a given uuid/pipeline pair.


    Parameters
    ----------
    uuid : str
        uuid of the product to be processed.
    pipeline : str
        Processing pipeline to process the product. Currently either "S1_UTM",
        "S1_WGS84", "S2".
        pipeline = 'S2' outputs a SAFE format package
        pipeline = 'S1*' outputs a geotiff format package

    Returns
    -------
    bool
        True when complete

    Raises
    ------
    warning
        If the processing pipeline fails. 
    """
    # get inventory file if not passed to function
    if inventory == None:
        inventory = gs_localmanager.get_product_inventory()

    # retrieve product dictionary
    # currently has explicit coding of pipeline, in case more added
    if pipeline == 'S1_UTM':
        #raise NotImplementedError('No support for S1 yet')
        try:
            new_fnames = _process_S1(uuid)
        except OSError as err:
            _not_processed_warning(uuid,err)
            return gs_localmanager.check_integrity()

        for f in new_fnames:
            add_S1_processed_to_inventory(uuid,f,pipeline)
        # not sure if necessary, but seems a good time to do an integ checking
        return gs_localmanager.check_integrity()

    if pipeline == 'S1_WGS84':
        try:
            new_fnames = _process_S1_WGS84(uuid)
        except OSError as err:
            _not_processed_warning(uuid,err)
            return gs_localmanager.check_integrity()

        for f in new_fnames:
            add_S1_processed_to_inventory(uuid,f, pipeline)
        # not sure if necessary, but seems a good time to do an integ checking
        return gs_localmanager.check_integrity()

    elif pipeline == 'S2':
        #raise NotImplementedError('No support for S2 yet')
        wd, fname = _generate_temp_copy(uuid)
        # do the processing
        try:
            _process_S2(wd,fname)
        except OSError as err:
            # in case of a crash, remove temp dir
            # and check integrity
            shutil.rmtree(wd)
            _not_processed_warning(uuid, err)
            return gs_localmanager.check_integrity()
        # move desired folder to data
        files = os.listdir(wd)

        #
        new_fname = [x for x in files if x.endswith('.SAFE') and x!=fname][0]

        # move to data dir
        shutil.move(os.path.join(wd,new_fname),os.path.join(DATA_PATH,new_fname))
        # remove temp
        shutil.rmtree(wd)
        add_S2_processed_to_inventory(uuid,new_fname,pipeline)
        # not sure if necessary, but seems a good time to do an integ checking
        return gs_localmanager.check_integrity()

    else:
        raise NotImplementedError('Unknown pipeline')


#### Sentinel 2 processing functions

def _process_S2(temp_directory,filename):
    """
    takes a product dictionary and processes file with sen2cor
    """
    p1 = subprocess.Popen([SEN2COR_ROOT_PATH,filename],
                            cwd=temp_directory,
                            stderr=subprocess.PIPE)
    response = p1.wait()
    if response > 0:
        string = p1.stderr.read().decode('utf')
        raise OSError('Sen2Cor Error: {}'.format(string))
    return None

def _generate_temp_copy(uuid,inventory=None):
    """
    generates a new folder for processing the safe files in
    """
    if inventory == None:
        inventory = gs_localmanager._get_inventory()

    fname = inventory[uuid]['filename']
    fname_temp = 'temp_'+fname
    # generate a new directory in data
    os.makedirs(os.path.join(DATA_PATH,fname_temp))
    # copy original SAFE into it
    shutil.copytree(os.path.join(DATA_PATH,fname),
                    os.path.join(DATA_PATH,fname_temp,fname))
    return os.path.join(DATA_PATH,fname_temp),fname

def add_S2_processed_to_inventory(uuid,new_file_name, pipeline, inventory=None):
    """
    makes a new product entry dict and uses gs_localmanager
    to add to inventory
    """
    # get inventory if not passed to function
    if inventory == None:
        inventory = gs_localmanager._get_inventory()

    # retrieve specific entry
    new_entry = inventory[uuid]

    # update process level to 'S2MSI1C'
    new_entry['producttype'] = 'S2MSI2A'
    new_entry['processinglevel'] = 'Level-2A'

    # update new_file_name
    new_entry['filename'] = new_file_name

    # update user processed flag
    new_entry['userprocessed'] = True
    new_entry['pipeline'] = pipeline

    # inventorise
    gs_localmanager.add_new_products({uuid:new_entry})
    return None

##################

# Sentinel 1 specific functions

def _process_S1_WGS84(uuid, inventory=None):
    # get inventory file if not passed to function
    if inventory == None:
        inventory = gs_localmanager._get_inventory()
    product_entry = inventory[uuid]
    # first input is always input files
    fname = product_entry['filename']
    # make a list of inputs
    args,outnames = _make_WGS84_geotiff_inputs(fname)
    command = '{0} {1} {2} {3}'.format(*args)
    # run process
    p1 = subprocess.Popen(command,shell=True)
    response = p1.wait()
    if response > 0:
        string = p1.stderr.read().decode('utf')
        raise OSError('SNAP Error: {}'.format(string))
    return outnames

def _make_WGS84_geotiff_inputs(fname):
    """
    WGS84 geotiff
    """
    # make a list of inputs
    graph = 's1_graphs/george_S1_GRD_Processing.xml'
    i1 ='-Pinput1="'+os.path.join(DATA_PATH,fname)+'"'
    outname1 = '{}_GRDL2_WGS84.tif'.format(os.path.join(DATA_PATH,fname.split('.')[0]))
    t1 = '-Ptarget1="{}"'.format(outname1)

    return [GPT_ROOT_PATH, graph, i1, t1],[outname1]

def _process_S1(uuid,inventory=None):
    """
    takes a product dictionary and processes file with S1 pipelineself.
    Currently only returns HDF5 files for 1 or 2 grid zones
    """
    # get inventory file if not passed to function
    if inventory == None:
        inventory = gs_localmanager._get_inventory()
    product_entry = inventory[uuid]
    # first input is always input files
    fname = product_entry['filename']
    # get a list of intersecting grid zones
    grid_zones = _get_UTM_zones(product_entry)

    # do the processing
    if len(grid_zones) == 1:
        # make a list of inputs
        args,outnames = _make_1zone_hdf_inputs(fname,grid_zones)
        command = '{0} {1} {2} {3} {4} {5}'.format(*args)
        # run process
        p1 = subprocess.Popen(command,shell=True)
        response = p1.wait()
        if response > 0:
            string = p1.stderr.read().decode('utf')
            raise OSError('SNAP Error: {}'.format(string))
        return outnames

    elif len(grid_zones) == 2:
        # make a list of inputs
        args,outnames = _make_2zone_hdf_inputs(fname,grid_zones)
        command = '{0} {1} {2} {3} {4} {5} {6} {7} {8}'.format(*args)
        # run process
        p1 = subprocess.Popen(command,shell=True)
        p1.wait()
        return outnames

    elif len(grid_zones) > 2:
        raise ValueError('Currently only support for 1 or 2 zone swaths')

def _make_2zone_hdf_inputs(fname,grid_zones):
    """
    2 zone hdf5
    """
    # make a list of inputs
    graph = 's1_graphs/2in_hdf5_2.xml'
    i1 ='-Pinput1="'+os.path.join(DATA_PATH,fname)+'"'
    i2 = '-Pinput2="{}"'.format(str(grid_zones[0][0]))
    i3 = '-Pinput3="{}"'.format(str(grid_zones[0][1]))
    i4 = '-Pinput4="{}"'.format(str(grid_zones[1][0]))
    i5 = '-Pinput5="{}"'.format(str(grid_zones[1][1]))
    outname1 = '{}_GRDL2_UTM{}.h5'.format(os.path.join(DATA_PATH,fname.split('.')[0]),
        str(grid_zones[0][0]))
    outname2 = '{}_GRDL2_UTM{}.h5'.format(os.path.join(DATA_PATH,fname.split('.')[0]),
        str(grid_zones[1][0]))
    t1 = '-Ptarget1="{}"'.format(outname1)
    t2 = '-Ptarget2="{}"'.format(outname2)

    return [GPT_ROOT_PATH, graph, i1, i2, i3, i4, i5, t1, t2], [outname1,outname2]

def _make_1zone_hdf_inputs(fname,grid_zones):
    """
    1 zone hdf5
    """
    # make a list of inputs
    graph = 's1_graphs/1in_hdf5_2.xml'
    i1 ='-Pinput1="'+os.path.join(DATA_PATH,fname)+'"'
    i2 = '-Pinput2="{}"'.format(str(grid_zones[0][0]))
    i3 = '-Pinput3="{}"'.format(str(grid_zones[0][1]))
    outname1 = '{}_GRDL2_UTM{}.h5'.format(os.path.join(DATA_PATH,fname.split('.')[0]),
        str(grid_zones[0][0]))
    t1 = '-Ptarget1="{}"'.format(outname1)

    return [GPT_ROOT_PATH, graph, i1, i2, i3, t1],[outname1]

def add_S1_processed_to_inventory(uuid,new_file_name, pipeline, inventory=None):
    """
    makes a new product entry dict and uses gs_localmanager
    to add to inventory
    """
    # get inventory file if not passed to function
    if inventory == None:
        inventory = gs_localmanager._get_inventory()

    # retrieve specific entry
    new_entry = inventory[uuid]

    # update process level to 'GRD_L2'
    new_entry['producttype'] = 'GRD_L2'

    # update new_file_name
    new_entry['filename'] = new_file_name

    # update user processed flag
    new_entry['userprocessed'] = True
    new_entry['pipeline'] = pipeline

    # inventorise
    gs_localmanager.add_new_products({uuid:new_entry})

    return None

################################
# general geospatial functions

def _get_UTM_zones(product_entry):
    """
    Takes a product entry dictionary and identifies the grid UTM_zones
    """
    UTMs = []

    # accept the single tile id from a sentinel 2
    if product_entry['platformname'] == 'Sentinel-2':
        return [_mgrs_to_UTMzone(product_entry['tileid'])]

    # accept the list of tile ids from a sentinel 1
    elif product_entry['platformname'] == 'Sentinel-1':
        for square in product_entry['tileid'][0]:
            UTMs.append(_mgrs_to_zone(square))
        unique = []
        for z in UTMs:
            if unique.count(z) == 0:
                unique.append(z)
        return unique
    else:
        raise NotImplementedError('Unknown satellite platform')

def _mgrs_to_zone(square):
    """
    Takes a MGRS grid square and returns zone and projection
    meridian
    """
    zone = int(square[:2])
    # convert char to number
    meridian = int(((360/60)*zone)-183)

    return zone, meridian

# warnings
def _prod_warning(uuid):
    warnings.warn("product {} is not a recognised data\
    type and cannot be processed".format(uuid))

# TODO implement better warnings
def _not_processed_warning(uuid, err):
    warnings.warn("product {} was not processed \n {}".format(uuid, err))
