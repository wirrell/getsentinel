"""
Import Sentinel-1 winter wheat data for the corresponding sheffield data set
fields.

NOTE: Only doing the first field for now to test - 12th July 2018
"""

from getsentinel import gs_downloader
from getsentinel import gs_localmanager
import datetime


# Test gs_downloader
test_file = 'test_files/CB7_4SS_grid_1 _combi.shp' 
start_season = datetime.date(2018, 5, 6)
end_season = datetime.date(2018, 5, 8)

s1_winterwheat_field = gs_downloader.ProductQueryParams()
s1_winterwheat_field.acquisition_date_range(start_season, end_season)
s1_winterwheat_field.product_details('S1', 'L1', 'GRD', 'IW', 'VV VH',
                                     orbitdirection='Ascending') 
s1_winterwheat_field.coords_from_file(test_file)  # MK44 2EE grid 3
s2_winterwheat_field = gs_downloader.ProductQueryParams()
s2_winterwheat_field.acquisition_date_range(start_season, end_season)
s2_winterwheat_field.product_details('S2', 'L2A', cloudcoverlimit=2)
s2_winterwheat_field.coords_from_file(test_file)

hub = gs_downloader.CopernicusHubConnection()

totals1, s1products = hub.submit_query(s1_winterwheat_field)
if totals1 is not 1:
    raise RuntimeError("gs_downloader test for Sentinel-1 products failed.")

totals2, s2products = hub.submit_query(s2_winterwheat_field)
if totals2 is not 2:
    raise RuntimeError("gs_downloader test for Sentinel-2 products failed.")

s2products = gs_downloader.filter_overlaps(s2products, s2_winterwheat_field.ROI)
if len(s2products) is not 1:
    raise RuntimeError("gs_downloader.filter_overlaps test failed.")

#hub.download_quicklooks(s2products)
#hub.download_products(s2products)
#hub.download_quicklooks(s1products)
#hub.download_products(s1products)

# Test gs_localmanager
gs_localmanager.check_integrity()
product_inventory = gs_localmanager.get_product_inventory()
