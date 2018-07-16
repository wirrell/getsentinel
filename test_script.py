"""
Import Sentinel-1 winter wheat data for the corresponding sheffield data set
fields.

NOTE: Only doing the first field for now to test - 12th July 2018
"""

from getsentinel import gs_downloader
from getsentinel import gs_localmanager
import pathlib
import datetime


# Test gs_downloader
test_file = pathlib.Path('test_files/CB7_4SS_grid_1 _combi.shp') 

s1_winterwheat_field = gs_downloader.ProductQueryParams()

start_season = datetime.date(2015, 9, 1)
end_season = datetime.date(2015, 9, 2)
s1_winterwheat_field.acquisition_date_range(start_season, end_season)
s1_winterwheat_field.product_details('S1', 'L1', 'GRD', 'IW', 'VV VH')
s1_winterwheat_field.coords_from_file(str(test_file),  # MK44 2EE grid 3
                                      '.shp',
                                      'BNG')
hub = gs_downloader.CopernicusHubConnection()
totals1, s1products = hub.submit_query(s1_winterwheat_field)
print(totals1)
hub.download_products(s1products)

# Test gs_localmanager
gs_localmanager.check_integrity()
product_inventory = gs_localmanager.get_product_inventory()
print(len(product_inventory))
