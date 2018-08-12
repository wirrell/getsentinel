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
start_season = date(2018, 5, 6)
end_season = date(2018, 5, 8)
ROI = '/path/to/roi.geojson'

roi_parameters = gs_downloader.ProductQueryParams()
roi_parameters.acquisition_date_range(start_season, end_season)
roi_parameter.product_details('S1', 'L1', 'GRD', 'IW', 'VV VH',
                                     orbitdirection='Ascending') 
roi_parameters.coords_from_file(ROI)

# submit a query to the ESA database
hub = gs_downloader.CopernicusHubConnection()
total, products = hub.submit_query(roi_parameters)

# download all the returned products
hub.download_products(products)
```




