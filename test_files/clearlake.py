from getsentinel import gs_downloader, gs_localmanager
from getsentinel import gs_stacker, gs_processor

start = date(2018, 7, 10)
end = date(2018, 8, 23)
# Build the query - Sentinel-2, Best Processing, 0% cloud cover
query = gs_downloader.Query('S2', start, end, 'clearlake.geojson')
query.product_details('BEST', cloudcoverlimit=0)
# Submit the query to Copernicus Hub and filter out product overlaps
hub = gs_downloader.CopernicusHubConnection()
total, products = hub.submit_query(query)
products = gs_downloader.filter_overlaps(products, query.ROI)
# Download the products
hub.download_products(products)
# Process the downloaded products to Level-2A
l2_products = gs_processor.batch_process(products)
# Call the stacker and extract the True Colour Image 10m resolution data
stacker = gs_stacker.Stacker(l2_products, 'clearlake.geojson', start, end)
stacker.set_bands(s2_band_list=['TCI'], s2_resolution=10)
data = stacker.generate_stacks()
TCI = data['clearlake']['TCI']
