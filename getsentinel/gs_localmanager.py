"""Downloaded product inventory manager.

This module provides an up-to-date product inventory and checks the integrity
of any saved inventory against the actual contents of the DATA_PATH provided by
the gs_config.

Example
-------

current_inventory = gs_localmanager.get_product_inventory()

new_downloaded_products = {uuid: product, uuid: product}

gs_localmanager.add_new_products(new_downloaded_products)

TODO
----
Add extra support for manual addition of S1 files to download directory.
"""

import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from .gs_config import DATA_PATH
from . import gs_downloader


def _get_new_uuid(uuid):
    # Produces a new uuid
    if 'user' not in uuid:
        return uuid + '-user'
    if uuid[-1].isdigit():  # if already numbered version
        num = int(uuid[-1]) + 1
        return uuid[:-1] + str(num)
    return uuid + '1'


def check_integrity():
    """Checks the integrity of the current inventory.

    Adds any products that were manually added to the DATA_PATH by the user
    since the last check. Removes any missing products.

    Returns
    -------
    bool
        True if successful, will throw an error otherwise.

    Raises
    ------
    RuntimeError
        If no unique match for a user added product can be found.
    RuntimeError
        If the user added product filename does not start with 'S1' or 'S2'

    """

    data_path = Path(DATA_PATH)
    data_path.mkdir(exist_ok=True)

    product_inventory = _get_inventory()

    # get all .SAFE file names from directory
    product_list_add = [x.name for x in list(data_path.glob('*.SAFE'))]
    # also get all processed files from directory
    procd_files = [x.name for x in list(data_path.glob('*')) if x.is_file() and
                   not x.suffix == '.json']
    # combine the two
    product_list_add = product_list_add + procd_files
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
        # return product
        if total is 0 or total > 1:
            # retry with a different part of the file name string
            search_term = 'filename:*' + filename[17:47] + '*'
            total, product = hub.raw_query(search_term)
            if total is 0 or total > 1:
                # if still now match, raise error.
                raise RuntimeError("Could not find a unique matching product"
                                   " in the ESA database for filename: \n"
                                   " {0} in the {1} directory."
                                   "".format(filename, DATA_PATH))
        for old_id in product:
            uuid = old_id
            product_info = product[uuid]
        product_info['userprocessed'] = True

        # TODO: write Sentinel-1 extra product info handling

        if product_info['platformname'] == 'Sentinel-2':
            file_info = list(Path(DATA_PATH + '/' + filename).glob('*MTD*'))
            # NOTE: this relies on xml info file structure remaining constant
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
                            product_info['tileid'] = tileid
        product_info['downloadlink'] = None
        product_info['filename'] = filename

        newid = _get_new_id(uuid) # noqa

        return newid, product_info

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
            newid, product_info = handle_user_prd(filename)
            new_products[newid] = product_info
            continue

        search_term = 'filename:*' + product_name + '*'
        total, product = hub.raw_query(search_term)
        if total is 0:  # assume it is a user processed file
            newid, product_info = handle_user_prd(filename)
        if total is 1:  # unique product found
            for uuid in product:
                newid = uuid
                product_info = product[uuid]
                product_info['filename'] = filename
        if total > 1:
            raise RuntimeError("Could not find a unique matching product"
                               " in the ESA database for filename: \n"
                               " {0} in the {1} directory."
                               "".format(filename, DATA_PATH))
        new_products[newid] = product_info

    for uuid in new_products:
        if uuid in product_inventory:
            new_uuid = _get_new_uuid(uuid)
        product_inventory[new_uuid] = new_products[uuid]

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
    """Returns the product inventory as a dictionary keyed by UUIDs.

    Returns
    -------
    product_inventory : dict
        Dictionary of products that are in the DATA_PATH directory, keyed by
        their UUIDs.

    """

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
    """Adds new products to the inventory.

    Note
    ----
    Used by the gs_downloader to log newly downloaded products. This function
    does not need to be called when you are downloading products via
    gs_downloader they are added to the inventory automatically.

    Returns
    -------
    added_uuids : list
        List of strings containing the UUIDs of the products that have been
        successfully added to the inventory."""

    product_inventory = _get_inventory()
    added_uuids = []

    for uuid in new_products:
        new_uuid = uuid
        if uuid in product_inventory:
            if product_inventory[uuid] == new_products[uuid]:
                print("Product {0} with UUID {1} is already"
                      " present in the product inventory."
                      " - Skipping"
                      "".format(new_products[uuid]['identifier'],
                                uuid))
                continue
            else:
                # product is a processed file
                new_products[uuid]['origin'] = uuid
            new_uuid = _get_new_uuid(uuid)
        product_inventory[new_uuid] = new_products[uuid]
        added_uuids.append(new_uuid)

    _save_product_inventory(product_inventory)

    return added_uuids
