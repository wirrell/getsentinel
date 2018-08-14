getsentinel
===========

## A download, process, and format pipeline for ESA Sentinel-X data.

### Authors: G. Worrall, J. Fennell

#### Requirements: 
                  Python 3.6
                  requests
                  mgrs
                  clint
                  shapely
                  pyshp
                  convertbng
                  rasterio
                  osgeo
                  numpy

Example Usage:

```
from getsentinel import gs_downloader
from datetime import date

# download Sentinel-1 products for a region of interest.
start_date = date(2018, 5, 6)
end_date = date(2018, 5, 8)
ROI = '/path/to/roi.geojson'

query = gs_downloader.Query()
query.acquisition_date_range(start_date, end_date)
query.product_details('S2', 'BEST', cloudcoverlimit=50) 
query.coords_from_file(ROI)

# submit a query to the ESA database
hub = gs_downloader.CopernicusHubConnection()
total, products = hub.submit_query(query)

# download all the returned products
hub.download_products(products)

# extract the data into a stack
stacker = gs_stacker.Stacker(products,
                            [ROI],
                            start_date,
                            end_date)

# set the bands to extract from the S2 products
stacker.set_bands(s2_band_list=['TCI'], s2_resolution = 10)

# 
stacker.check_weather(cloud=20, snow=20)

stacks = stacker.generate_stacks()

```




