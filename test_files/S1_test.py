"""
Test the downloader for Sentinel-1 products
"""

from getsentinel import gs_downloader
from getsentinel import gs_localmanager
import datetime


# Test gs_downloader
test_file = 'test_field.geojson' 
start = datetime.date(2018, 5, 6)
end = datetime.date(2018, 5, 7)

query = gs_downloader.Query('S1', start, end, test_file)
query.product_details('L1', 'GRD', 'IW', 'VV VH',
                      orbitdirection='Ascending') 

hub = gs_downloader.CopernicusHubConnection()

totals1, s1products = hub.submit_query(query)
if totals1 is not 1:
    raise RuntimeError("gs_downloader test for Sentinel-1 products failed.")

hub.download_quicklooks(s1products)
hub.download_products(s1products)
