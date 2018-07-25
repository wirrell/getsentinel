"""
Downloaded product inventory manager.

    TODO:
        Check support for manual addition of S1 files to download directory.
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from .gs_config import DATA_PATH
from . import gs_downloader


def check_integrity():

    """Checks the integrity of the current inventory."""

    data_path = Path(DATA_PATH)
    data_path.mkdir(exist_ok=True)

    product_inventory = _get_inventory()

    # get all file names from directory
    product_list_add = [x.name for x in list(data_path.glob('*.SAFE'))]
    product_inventory_gone = product_inventory.copy()

    for uuid, product in product_inventory.items():
        if product['filename'] in product_list_add:
            product_inventory_gone.pop(uuid, None)
            product_list_add.remove(product['filename'])

    for uuid in product_inventory_gone:  # now holds inventory entries for
        product_inventory.pop(uuid, None)  # product that no longer exist

    def handle_user_prd(filename):

        """
        Retrieves info for user processed files from both the ESA hub and
        any included xml info file.
        """

        search_term = 'filename:*' + filename[25:60] + '*'
        # query the ESA hub for the original product data
        total, product = hub.raw_query(search_term)
        if total is 0 or total > 1:
            raise RuntimeError("Could not find a unique matching product"
                               "in the ESA database for filename: \n"
                               " {0} in the {1} directory."
                               "".format(filename, DATA_PATH))
        for uuid in product:
            product_info = product[uuid]
        product_info['userprocessed'] = True

        file_info = list(Path(DATA_PATH + '/' + filename).glob('*MTD*'))
        # NOTE: this relies on the xml info file structure remaining constant
        with open(file_info[0], 'r') as read_in:
            file_info_tree = ET.parse(read_in)
            root = file_info_tree.getroot()
            product_info['identifier'] = filename[:-5]
            required_tags = ['PROCESSING_LEVEL',
                             'PRODUCT_TYPE',
                             'PROCESSING_BASELINE']
            available_tags = []
            for child in root[0][0]:
                available_tags.append(child.tag)
            for req_tag in required_tags:
                if req_tag not in available_tags:
                    raise RuntimeError("Manifest at location {0} does not"
                                       " conform to expected structure."
                                       "".format(file_info[0]))
            for child in root[0][0]:
                if child.tag == 'PROCESSING_LEVEL':
                    product_info['processinglevel'] = child.text
                if child.tag == 'PRODUCT_TYPE':
                    product_info['producttype'] = child.text
                if child.tag == 'PROCESSING_BASELINE':
                    product_info['processingbaseline'] = child.text
                if child.tag == 'L2A_Product_Organisation':
                    if 'tileid' not in product_info:
                        # hack to pull out tileid
                        tileid = child[0][0][0].text[-13:-8]
                        print(tileid)
                        product_info['tileid'] = tileid
            product_info['downloadlink'] = None
            product_info['filename'] = filename

        for uuid in product:
            newid = uuid + '-user'
        product[newid] = product.pop(uuid)

        return product

        # TODO: check manual addition of S1 files to download directory doesn't
        # cause issues.
    new_products = {}

    for filename in product_list_add:
        print("Adding user added file {0} to product"
              " inventory.".format(filename))
        if not (filename.startswith('S1') or filename.startswith('S2')):
            raise RuntimeError("Custom product file renaming is not"
                               " supported. Product names must start with"
                               " 'S1' or 'S2' and follow standard naming"
                               " conventions. \n See"
                               " https://scihub.copernicus.eu/userguide/")
        hub = gs_downloader.CopernicusHubConnection()
        product_name = filename[:-5]
        if 'USER_PRD' in product_name:
            # files already user processed require special case handling
            product = handle_user_prd(filename)
            for uuid in product:
                new_products[uuid] = product[uuid]
            continue

        search_term = 'filename:*' + product_name + '*'
        total, product = hub.raw_query(search_term)
        if total is 0:  # assume it is a user processed file
            product = handle_user_prd(filename)
        if total > 1:
            raise RuntimeError("Could not find a unique matching product"
                               "in the ESA database for filename: \n"
                               " {0} in the {1} directory."
                               "".format(filename, DATA_PATH))
        for uuid in product:
            new_products[uuid] = product[uuid]

    for uuid in new_products:
        product_inventory[uuid] = new_products[uuid]

    _save_product_inventory(product_inventory)

    return True


def _get_inventory():

    """"Retrieves the product inventory from .json file."""

    product_inventory_path = Path(DATA_PATH + '/product_inventory.json')
    product_inventory_path.touch(exist_ok=True)
    try:
        with product_inventory_path.open() as read_in:
            product_inventory = json.load(read_in)
    except (ValueError, TypeError):  # if the inventory is empty
        product_inventory = {}

    return product_inventory


def get_product_inventory():

    """Returns the product inventory as a dictionary of UUIDs."""

    check_integrity()

    product_inventory = _get_inventory()

    return product_inventory


def _save_product_inventory(product_inventory):

    """Writes the updated product inventory to the associated .json file."""

    product_inventory_path = Path(DATA_PATH + '/product_inventory.json')
    product_inventory_path.touch(exist_ok=True)
    with product_inventory_path.open(mode='w') as write_out:
        json.dump(product_inventory, write_out)


def add_new_products(new_products: dict):

    """Adds new products to the inventory."""

    def get_new_uuid(uuid):
        # Produces a new uuid
        if 'user' not in uuid:
            return uuid + '-user'
        if uuid[-1].isdigit():  # if already numbered version
            num = int(uuid[-1]) + 1
            return uuid[:-1] + str(num)

    product_inventory = _get_inventory()
    added_uuids = []

    for uuid in new_products:
        if uuid in product_inventory:
            if product_inventory[uuid] == new_products[uuid]:
                raise RuntimeError("Product {0} with UUID {1} is already"
                                   " present in the product inventory."
                                   "".format(new_products[uuid]['identifier'],
                                             uuid))
            new_uuid = get_new_uuid(uuid)
        product_inventory[new_uuid] = new_products[uuid]
        added_uuids.append(new_uuid)

    _save_product_inventory(product_inventory)

    return added_uuids
