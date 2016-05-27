import os
from datetime import datetime

import netCDF4
import numpy

from cablab import NetCDFCubeSourceProvider


class BurntAreaProvider(NetCDFCubeSourceProvider):
    def __init__(self, cube_config, name='burnt_area', dir=None):
        super(BurntAreaProvider, self).__init__(cube_config, name, dir)
        self.old_indices = None

    @property
    def variable_descriptors(self):
        return {
            'burned_area': {
                'source_name': 'BurntArea',
                'data_type': numpy.float32,
                'fill_value': -9999.0,
                'units': 'hectares',
                # TODO I think much more useful would be burned_area_fraction, because it does note depend on grid cell size. Can we calculate this instead?
                # 'long_name': 'Monthly Burnt Area',
                'standard_name': 'burned_area',
                'references' : 'Giglio, Louis, James T. Randerson, and Guido R. Werf. "Analysis of daily, monthly, and annual burned area using the fourth‐generation global fire emissions database (GFED4)." Journal of Geophysical Research: Biogeosciences 118.1 (2013): 317-328.',
                'comment' : 'Burnt Area based on the GFED4 fire product.',
                'scale_factor': 1.0,
                'add_offset': 0.0,
                'url': 'http://www.globalfiredata.org/',
            }
        }

    def compute_source_time_ranges(self):
        source_time_ranges = []
        file_names = os.listdir(self.dir_path)
        for file_name in file_names:
            file = os.path.join(self.dir_path, file_name)
            dataset = self.dataset_cache.get_dataset(file)
            time_bnds = dataset.variables['time_bnds']
            # todo (nf 20151028) - check datetime units, may be wrong in either the netCDF file (which is
            # 'days since 1582-10-14 00:00') or the netCDF4 library
            dates1 = netCDF4.num2date(time_bnds[:, 0], 'days since 1582-10-24 00:00', calendar='gregorian')
            dates2 = netCDF4.num2date(time_bnds[:, 1], 'days since 1582-10-24 00:00', calendar='gregorian')
            self.dataset_cache.close_dataset(file)
            for i in range(len(dates1)):
                t1 = datetime(dates1[i].year, dates1[i].month, dates1[i].day)
                t2 = datetime(dates2[i].year, dates2[i].month, dates2[i].day)
                source_time_ranges.append((t1, t2, file, i))
        return sorted(source_time_ranges, key=lambda item: item[0])
