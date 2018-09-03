"""
Sentinel-2 Test

Download Sentinel-2 data for the test field.
"""

from getsentinel import gs_downloader
from getsentinel import gs_stacker
from getsentinel import gs_processor
import datetime

# Test gs_downloader
test_file = 'test_field.geojson'
start_season = datetime.date(2018, 6, 6)
end_season = datetime.date(2018, 6, 6)

query = gs_downloader.Query('S2', start_season, end_season, test_file)
query.product_details('L1C')

hub = gs_downloader.CopernicusHubConnection()
total, products = hub.submit_query(query)
products = gs_downloader.filter_overlaps(products,
                                         query.ROI)
hub.download_products(products)

# Test processor
new_products = gs_processor.batch_process(products)

# Test stacker
stacker = gs_stacker.Stacker(new_products,
                             test_file,
                             datetime.date(2018, 1, 6),
                             end_season)

s2_valid_bands = {'10': ['AOT', 'B02', 'B03', 'B04', 'B08', 'TCI',
                         'WVP'],
                  '20': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                         'B07', 'B08A', 'B11', 'B12', 'SCL', 'TCI',
                         'WVP'],
                  '60': ['AOT', 'B02', 'B03', 'B04', 'B05', 'B06',
                         'B07', 'B08A', 'B09', 'B11', 'B12', 'SCL',
                         'TCI', 'WVP']}

for res in s2_valid_bands:
    stacker.set_bands(s2_band_list=s2_valid_bands[res], s2_resolution=res)
    stacker.check_weather(cloud=20, snow=20)

    stacks = stacker.generate_stacks()

    for stack in stacks:
        for band in stacks[stack]:
            print(band)
