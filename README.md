getsentinel
===========

## A download, process, and masking pipeline for ESA Sentinel-X data.

### Author: G. Worrall

#### Requirements: 
                  Python 3.6
                  requests
                  clint
                  pyshp
                  geojson
                  shapely
                  osgeo
                  numpy
                  rasterio

Example Usage:

```
from getsentinel import gs_downloader, gs_stacker
from datetime import date

# download Sentinel-2 products for a region of interest.
start_date = date(2018, 5, 6)
end_date = date(2018, 5, 8)
ROI = '/path/to/roi.geojson'

query = gs_downloader.Query('S2', start_date, end_date, ROI)
query.product_details('BEST', cloudcoverlimit=50) 

# submit a query to the ESA database
hub = gs_downloader.CopernicusHubConnection()
total, products = hub.submit_query(query)
# download all the returned products
hub.download_products(products)

# process all the downloaded products
processed = gs_processor.batch_process(products)

# extract the data into a stack
stacker = gs_stacker.Stacker(products,
                             ROI,
                             start_date,
                             end_date)

# set the bands to extract from the S2 products
stacker.set_bands(s2_band_list=['TCI'], s2_resolution = 10)
# check the Sentinel weather masks for ROI coverage
stacker.check_weather(cloud=20, snow=20)

data = stacker.generate_stacks()

```




