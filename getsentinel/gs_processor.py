"""Channels under-processed products to the relevant ESA processing tools.

This modules takes an individual downloaded product UUID and processing the
corresponding product. The resultant processed product is stored in the product
inventory and the new UUID under which it is stored is returned.

Note
----
Sentinel-2 products that are not Level-1C will be skipped and their current
uuids and product info returned.

Example
-------

from getsentinel import gs_process

level1c_s2products = {uuid: info, uuid: info}

for uuid in level1c_s2products:
    level2a_s2products = gs_process.batch_process(uuid)

"""
# TODO: Implement processed project inventory checking to prevent re-processing
# products that have already been processed.


from pathlib import Path
import shutil
import subprocess
from . import gs_localmanager, gs_config


def batch_process(product_inventory, gpt_graph=False):
    """Processes a batch of product and returns the new processed products
    uuids and info.

    Parameters
    ----------
    product_inventory : dict
        Contains products as supplied in {uuid: info, uuid: info} format.
    gpt_graph : str, optional
        The path to the gpt tool graph to be used to process any Sentinel-1
        products supplied.

    Returns
    -------
    dict
        Contains the new processed product uuids and info.

    """

    processed_products = {}

    for uuid in product_inventory:
        new_uuid, new_info = process(uuid, gpt_graph)
        processed_products[new_uuid] = new_info

    return processed_products


def process(uuid, gpt_graph=False):
    """Channels a product through the corresponding ESA processing tool.

    Parameters
    ----------
    uuid : str
        UUID of the product to be processed.
    gpt_graph : str, optional
        The path to the gpt tool graph to be used to process a Sentinel-1
        product.

    Returns
    -------
    str
        The UUID of the newly generated processed product as it appears in the
        product inventory.
    dict
        Contains the new product info with parameters changed to reflect the
        processing that has occured.

    """

    inventory = gs_localmanager.get_product_inventory()

    product = inventory[uuid]
    platform = product['platformname']

    if platform == 'Sentinel-1':
        if not gpt_graph:
            raise RuntimeError("You must supply a SNAP generated Sentinel-1 "
                               "processing .xml graph file when processing "
                               " Sentinel-1 products.")
        new_uuid, new_product = _s1process(uuid, product, gpt_graph)

    if platform == 'Sentinel-2':
        new_uuid, new_product = _s2process(uuid, product)

    if platform == 'Sentinel-3':
        raise NotImplementedError

    return new_uuid, new_product


def _s1process(uuid, product, gpt_graph):
    """Processed the product using gpt tool."""

    if product['producttype'] != 'GRD':
        raise NotImplementedError("Only GRD Sentinel-1 files currently "
                                  "supported.")

    infile = Path(gs_config.DATA_PATH).joinpath(product['filename'])
    intarget = '-Pinput1="{0}"'.format(infile)

    graph_name = gpt_graph.split('.')[0]
    outname = infile.stem + '_PROC_{0}.tif'.format(graph_name)
    outfile = infile.with_name(outname)
    outtarget = '-Ptarget1="{0}"'.format(outfile)

    gpt = gs_config.GPT_ROOT_PATH

    gdal_conf = 'LD_LIBRARY_PATH=.'

    command = '{0} {1} {2} {3} {4}'.format(gdal_conf, gpt, gpt_graph, intarget,
                                           outtarget)

    print(command)

    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        for line in process.stdout:
            print(line.decode().strip())
    except KeyboardInterrupt:
        outfile.unlink()
        raise KeyboardInterrupt

    new_uuid, new_product = _add_processed(uuid, product, outfile,
                                           gpt_graph=gpt_graph)

    return new_uuid, new_product


def _s2process(uuid, product):
    """Process a Level 1C Sentinel-2 file using S2."""

    # Skip downloaded products that are Level-2A already
    if '2A' in product['processinglevel']:
        return uuid, product

    filename = product['filename']
    filepath = Path(gs_config.DATA_PATH).joinpath(filename)
    # NOTE: This is per the sen2cor renaming convention. May break.
    outname = filename[:8] + '2A' + filename[10:]
    outpath = Path(gs_config.DATA_PATH).joinpath(outname)

    try:
        process = subprocess.Popen([gs_config.SEN2COR_ROOT_PATH, filepath],
                                   stdout=subprocess.PIPE)

        for line in process.stdout:
            print(line.decode().strip())
    except KeyboardInterrupt:
        process.kill()
        shutil.rmtree(outpath)
        raise KeyboardInterrupt

    new_uuid, new_product = _add_processed(uuid, product, outname, 'Level-2A',
                                           'S2MSI2A')

    return new_uuid, new_product


def _add_processed(uuid, product, newfilename, proclevel=False, prodtype=False,
                   gpt_graph=False):
    """Adds a new processed product to the product inventory."""

    product['userprocessed'] = True
    product['filename'] = newfilename
    product['identifier'] = newfilename.split('.')[0]
    if proclevel:
        product['processinglevel'] = proclevel
    if prodtype:
        product['producttype'] = prodtype
    if gpt_graph:
        product['gpt_graph'] = gpt_graph
    product['origin'] = uuid

    # One product added, returns a list containing a single id
    new_uuid = gs_localmanager.add_new_products({uuid: product})[0]

    return new_uuid, product
