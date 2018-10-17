"""Downloaded product inventory manager.

This module provides an up-to-date product inventory and checks the integrity
of any saved inventory against the actual contents of the DATA_PATH provided by
the gs_config.

Products are stored as dictionaries containing all the necessary product info.
See below for example product info format.

Example
-------

current_inventory = gs_localmanager.get_product_inventory()

new_downloaded_products = {uuid: product, uuid: product, ...}

gs_localmanager.add_new_products(new_downloaded_products)

Example Product Info Format
---------------------------
Below is an example format, as stored in the product_inventory.json, of an
unprocessed Sentinel-1 product. The keys `tileid` and `userprocessed` are
added by the gs_downloader module. The former denotes the Senntinel-2 MGRS
tiles that the product traverses, the latter indicates whether the file has
been processed. For processed products a further field, `origin`, is added
which contains the UUID of the unprocessed product from which the processed
product originates.

    {'acquisitiontype': 'NOMINAL',
     'beginposition': '2015-08-24T06:22:07.95Z',
     'downloadlink': "https://scihub.copernicus.eu/dhus/odata/v1/Products ... "
     'endposition': '2015-08-24T06:22:32.949Z',
     'filename': 'S1A_IW_GRDH_1SDV_20150824T062207_20150824T062232_007401 ... '
     'footprint': 'POLYGON ((-0.059059 53.057114,-3.867077 53.461575)) '
     'format': 'SAFE',
     'gmlfootprint': '<gml:Polygon footprint ...'
     'identifier': 'S1A_IW_GRDH_1SDV_20150824T062207_20150824T062232_007401 ... '
     'ingestiondate': '2015-08-24T15:55:01.836Z',
     'instrumentname': 'Synthetic Aperture Radar (C-band)',
     'instrumentshortname': 'SAR-C SAR',
     'lastorbitnumber': '7401',
     'lastrelativeorbitnumber': '154',
     'missiondatatakeid': '41709',
     'orbitdirection': 'DESCENDING',
     'orbitnumber': '7401',
     'origin': 'd42cc6fe-5f81-4753-bf61-dc081af8fa68',
     'platformidentifier': '0000-000A',
     'platformname': 'Sentinel-1',
     'polarisationmode': 'VV VH',
     'productclass': 'S',
     'producttype': 'GRD',
     'quicklookdownload': "https://scihub.copernicus.eu/dhus/ ... "
     'relativeorbitnumber': '154',
     'sensoroperationalmode': 'IW',
     'size': '1 GB',
     'slicenumber': '6',
     'status': 'ARCHIVED',
     'swathidentifier': 'IW',
     'tileid': [['30UVE', ...]]
     'userprocessed': False}

"""

import json
import warnings
from pathlib import Path
from .gs_config import DATA_PATH
from . import gs_downloader


def _get_new_uuid(uuid):
    """Generates a new uuid."""
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

    Note
    ----
    Any manually added products that have already been processed must be
    explicitly added via `add_new_products`.

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
    UserWarning
        If a processed product is manually added to the `DATA_PATH` without
        having been added to the inventory by called `add_new_products`.

    """

    data_path = Path(DATA_PATH)
    data_path.mkdir(exist_ok=True)

    product_inventory = _get_inventory()

    # get all .SAFE file names from directory
    product_list_add = [x.name for x in list(data_path.glob('*.SAFE'))]
    # also get all processed files from directory
    # NOTE: need to add the random apple files Joe mentioned to be ignored
    # here.
    other_files = [x.name for x in list(data_path.glob('*')) if x.is_file() and
                   not x.suffix == '.json']

    product_inventory_gone = product_inventory.copy()

    for uuid, product in product_inventory.items():
        if product['filename'] in product_list_add:
            product_inventory_gone.pop(uuid, None)
            product_list_add.remove(product['filename'])
        # remove any processed files from the list that are already
        # inventorised.
        if product['filename'] in other_files:
            product_inventory_gone.pop(uuid, None)
            other_files.remove(product['filename'])

    # any left over files in other_files will be un-inventorised processed
    # files and a user warning should be raised.
    if len(other_files) != 0:
        warnings.warn("Any manually added processed files must be explicitly"
                      " added to the product inventory using the"
                      " gs_localmanager.add_new_products function.")

    for uuid in product_inventory_gone:  # now holds inventory entries for
        product_inventory.pop(uuid, None)  # product that no longer exist

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

        # skip all user produced files.
        if 'USER_PRD' in product_name:
            warnings.warn("Any manually added processed files must be"
                          " explicitly added to the product inventory using"
                          " the gs_localmanager.add_new_products function.")
            continue

        search_term = 'filename:*' + product_name + '*'
        total, product = hub.raw_query(search_term)
        if total is 1:  # matching ESA database product found
            for uuid in product:
                product_info = product[uuid]

        if total > 1 or total is 0:
            # couldn't find a unique product.
            # this should almost never be != 1 unless someone has explicitly
            # changed the file name of their manually added product
            raise RuntimeError("Could not find a unique matching product"
                               " in the ESA database for filename: \n"
                               " {0} in the {1} directory."
                               "".format(filename, DATA_PATH))

        new_products[uuid] = product_info

    for uuid in new_products:
        product_inventory[uuid] = new_products[uuid]

    _save_product_inventory(product_inventory)

    return True


def _get_inventory():
    """"Retrieves the product inventory from .json file."""

    product_inventory_path = Path(DATA_PATH).joinpath('product_inventory.json')
    product_inventory_path.touch(exist_ok=True)
    try:
        with product_inventory_path.open() as read_in:
            product_inventory = json.load(read_in)
    except (ValueError, TypeError):  # if the inventory is empty
        product_inventory = {}

    return product_inventory


def get_product_inventory():
    """Returns the product inventory as a dictionary keyed by product UUIDs.

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

    product_inventory_path = Path(DATA_PATH).joinpath('product_inventory.json')
    product_inventory_path.touch(exist_ok=True)
    with product_inventory_path.open(mode='w') as write_out:
        json.dump(product_inventory, write_out)


def add_new_products(new_products: dict):
    """Adds new products to the inventory.

    Note
    ----
    This function should be used to add processed products that have been
    manually added by the user.
    This function does not need to be called when you are downloading products
    via gs_downloader as they are added to the inventory automatically.

    Returns
    -------
    added_uuids : list
        List of strings containing the UUIDs of the products that have been
        successfully added to the inventory.
        
    """

    product_inventory = _get_inventory()
    added_uuids = []

    for uuid in new_products:
        new_uuid = uuid
        if new_uuid in product_inventory:
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
