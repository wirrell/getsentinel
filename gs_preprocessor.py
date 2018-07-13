"""
Script to invoke the sen2cor processor for S2 and gpt for S1
TODO:
    class for invoking processors
    class for pulling
@author: Joe Fennell
"""

import gs_config
import gs_localmanager
import xml.etree.ElementTree as ET

pipelines = {'S2':{'instrumentshortname':'MSI',
                      'commandlineprocessor':'L2A_Process',
                      'options':[]},
             'S1_default':{'instrumentshortname':'SAR-C SAR',
             'commandlineprocessor':'s1tbx',
             'graphfiletemplate':'google_graph.xml'}}

def get_processable_files(inventory=None, ignore_processed=True):
    """
    Checks the inventory file for compatible file types which have
    not yet been processed.
    Returns: dictionary where key is the UUID and value is the pipeline

    # for now  make a simple version which just handles S1 and S2
    """
    pass


# radar specific functions
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
