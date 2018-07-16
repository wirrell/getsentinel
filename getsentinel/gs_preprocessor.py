"""
Script to invoke the sen2cor processor for S2 and gpt for S1
TODO:
    class for invoking processors
    product_entry fields to modify:

@author: Joe Fennell
"""

from . import gs_config
from . import gs_localmanager
import xml.etree.ElementTree as ET
import warnings

pipelines = {'S2':{'producttype':'S2L1C',
                      'commandlineprocessor':'L2A_Process',
                      'options':[]},
             'S1':{'instrumentshortname':'GRD',
             'commandlineprocessor':'s1tbx',
             'graphfiletemplate':'google_graph.xml'}}

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
            prod_warning(uuid)

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


# warnings
def prod_warning(uuid):
    warnings.warn("product {} is not a recognised data\
    type and cannot be processed".format(uuid))

# MSI specific functions

# radar specific functions

def add_S1_processed_to_inventory(UUID,product_entry):
    """
    makes a new product entry dict and adds to inventory_entry
    """
    pass

def get_UTM_zones(product_entry):
    """
    Takes an product entry dictionary and identifies the grid UTM_zones
    """
    pass

def make_s1_graph_file(graph_file_template,inventory_entry):
    """
    Takes a graph file template and produces a new temp graph_file for
    a given S1 file
    """
    pass


# controller classes
class processor(object):

    """
    Major class for handling the processing pipelines
    """

    def __init__(self,pipelines=pipelines):

        self.pipelines = pipelines
        pass

    #def
