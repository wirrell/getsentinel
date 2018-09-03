getsentinel documentation
=======================================

`getsentinel` is a Python package for automating the downloading, processing
and extraction of Sentienl data.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   Installation<installation.rst>


Quick Start Example
-------------------
::

    from datetime import date
    from getsentinel import gs_downloader, gs_processor, gs_stacker

    roi = 'region_of_interest.shp'

    start = date(2018, 1, 1)
    end = date(2018, 1, 7)

    query = gs_downloader.Query('S2', start, end, roi)
    query.product_details('L1C', cloudcoverlimit=0)

    hub = gs_downloader.CopernicusHubConnection()
    num_results, products = hub.submit_query(query)

    processed = gs_processor.batch_process(products)

    stacker = gs_stacker.Stacker(processed, roi, start, end)
    stacker.set_bands(s2_band_list=['B02', 'B03', 'B04'])

    data_output = stacker.generate_stacks()



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
