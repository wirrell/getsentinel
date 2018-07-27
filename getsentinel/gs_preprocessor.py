"""
Script to invoke the sen2cor processor for S2 and gpt for S1
TODO:
    class for invoking processors
    product_entry fields to modify:

@author: Joe Fennell
"""

from . import gs_localmanager
from .gs_config import SEN2COR_ROOT_PATH, DATA_PATH
import xml.etree.ElementTree as ET
import warnings
import os, shutil, subprocess

def get_processable_files(inventory=None, ignore_processed=True):
    """
    Checks the inventory file for compatible file types which have
    not yet been processed.
    Returns: dictionary where key is the UUID and value is the pipeline

    # for now  make a simple version which just handles S1 and S2
    """

    # get a product inventory if none supplied.
    # A restricted or prefiltered inventory could be supplied
    # if, for example a certain geographic restriction was needed

    if inventory == None:
        inventory = gs_localmanager.get_product_inventory()

    # apply set logic
    unprocessed_S2L1C = set()
    #unprocessed_S2L2A = set()
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
            #unprocessed_S2L2A.add(uuid)
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
        out[uuid] = 'S1'

    return out


def process(uuid,pipeline,inventory=None):
    """
    Runs the processing operation for a given uuid/pipeline pair.

    Arguments:
    uuid - uuid of product
    pipeline - currently either "S1" or "S2"
    """
    # get inventory file if not passed to function
    if inventory == None:
        inventory = gs_localmanager.get_product_inventory()

    # retrieve product dictionary
    product_entry = inventory[uuid]
    # currently has explicit coding of pipeline, in case more added
    if pipeline == 'S1':
        raise NotImplementedError('No support for S1 yet')
        new_fname = _process_S1(product_entry)
        add_S1_processed_to_inventory(uuid,new_fname)
        # not sure if necessary, but seems a good time to do an integ checking
        return gs_localmanager.check_integrity()

    elif pipeline == 'S2':
        #raise NotImplementedError('No support for S2 yet')
        wd, fname = _generate_temp_copy(uuid)
        # do the processing
        _process_S2(wd,fname)
        # move desired folder to data
        files = os.listdir(wd)

        #
        new_fname = [x for x in files if x.endswith('.SAFE') and x!=fname][0]

        # move to data dir
        shutil.move(os.path.join(wd,new_fname),os.path.join(DATA_PATH,new_fname))
        # remove temp
        shutil.rmtree(wd)
        add_S2_processed_to_inventory(uuid,new_fname)
        # not sure if necessary, but seems a good time to do an integ checking
        return gs_localmanager.check_integrity()

    else:
        raise NotImplementedError('Unknown pipeline')

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

# warnings
def _prod_warning(uuid):
    warnings.warn("product {} is not a recognised data\
    type and cannot be processed".format(uuid))

# MSI specific functions
def add_S2_processed_to_inventory(uuid,new_file_name, inventory=None):
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
    new_entry['producttype'] = 'S2MSI1C'
    new_entry['processinglevel'] = 'Level-2A'

    # update new_file_name
    new_entry['filename'] = new_file_name

    # update user processed flag
    new_entry['userprocessed'] = True

    # inventorise
    gs_localmanager.add_new_products({uuid:new_entry})
    return None

def _process_S2(temp_directory,filename):
    """
    takes a product dictionary and processes file with sen2cor
    """
    subprocess.Popen([SEN2COR_ROOT_PATH,filename],cwd=temp_directory)

    return None
# radar specific functions

def add_S1_processed_to_inventory(uuid,new_file_name, inventory=None):
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

    # inventorise
    gs_localmanager.add_new_products({uuid:new_entry})
    return None

# general geospatial functions

def _get_UTM_zones(product_entry):
    """
    Takes a product entry dictionary and identifies the grid UTM_zones
    """
    UTMs = []

    # accept the single tile id from a sentinel 2
    if product_entry['platformname'] == 'Sentinel-2':
        return [mgrs_to_UTM(product_entry['tileid'])]

    # accept the list of tile ids from a sentinel 1
    elif product_entry['platformname'] == 'Sentinel-1':
        for square in product_entry['tileid']:
            UTMs.append(mgrs_to_UTMzone(square))
        unique = []
        for z in UTMs:
            if unique.count(z) == 0:
                unique.append(z)
        return unique
    else:
        raise NotImplementedError('Unknown satellite platform')

def _mgrs_to_UTMzone(square):
    """
    Takes a MGRS grid square and returns zone and hemisphere
    """
    zone = int(square[:2])
    # convert char to number
    band = ord(square[2])-64
    if band > 13:
        return zone, 'N'
    else:
        return zone, 'S'


def _make_s1_graph_file(graph_file_template,inventory_entry):
    """
    Takes a graph file template and produces a new temp graph_file for
    a given S1 file
    """
    return filename

def _process_S1(product_entry):
    """
    takes a product dictionary and processes file with S1 pipeline
    """
    grid_zones = _get_utm_zones(product_entry)
    return filename
