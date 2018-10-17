import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='getsentinel',
    version='0.1',
    description='An ESA Sentinel data pipeline.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://bitbucket.org/wirrell/getsentinel',
    author='G. Worrall',
    author_email='worrall.george@gmail.com',
    license='Apache 2.0',
    packages=setuptools.find_packages(),
    python_requires='>=3.4',
    install_requires=[
        'requests',
        'clint',
        'pyshp',
        'geojson',
        'shapely',
        'numpy',
        'rasterio'],
    project_urls={
        'Documentation': 'https://getsentinel.readthedocs.io/',
        'Source': 'https://www.bitbucket.org/wirrell/getsentinel'}
    )
