from datetime import datetime, timedelta
import os

import numpy
import netCDF4

from cablab import BaseCubeSourceProvider
from cablab.util import NetCDFDatasetCache, aggregate_images

VAR_NAME = 't2m'


class AirTemperatureProvider(BaseCubeSourceProvider):
    def __init__(self, cube_config, dir_path):
        super(AirTemperatureProvider, self).__init__(cube_config)
        # todo (nf 20151028) - remove check once we have addressed spatial aggregation/interpolation, see issue #3
        if cube_config.grid_width != 1440 or cube_config.grid_height != 720:
            raise ValueError('illegal cube configuration, '
                             'provider does not yet implement proper spatial aggregation/interpolation')
        self.dir_path = dir_path
        self.source_time_ranges = None
        self.dataset_cache = NetCDFDatasetCache(VAR_NAME)
        self.old_indices = None

    def prepare(self):
        self._init_source_time_ranges()

    def get_variable_descriptors(self):
        return {
            VAR_NAME: {
                'data_type': numpy.float32,
                'fill_value': -32767,
                'units': 'K',
                'long_name': '2 metre temperature',
                'scale_factor': 0.0019718202938428923,
                'add_offset': 259.2678739531343,
            }
        }

    def compute_variable_images_from_sources(self, index_to_weight):

        # close all datasets that wont be used anymore
        new_indices = set(index_to_weight.keys())
        if self.old_indices:
            unused_indices = self.old_indices - new_indices
            for i in unused_indices:
                file, time_index = self._get_file_and_time_index(i)
                self.dataset_cache.close_dataset(file)
        self.old_indices = new_indices

        if len(new_indices) == 1:
            i = next(iter(new_indices))
            file, time_index = self._get_file_and_time_index(i)
            dataset = self.dataset_cache.get_dataset(file)
            air_temperature = dataset.variables[VAR_NAME][time_index, 0:720, :]
        else:
            images = [None] * len(new_indices)
            weights = [None] * len(new_indices)
            j = 0
            for i in new_indices:
                file, time_index = self._get_file_and_time_index(i)
                dataset = self.dataset_cache.get_dataset(file)
                variable = dataset.variables[VAR_NAME]
                images[j] = variable[time_index, 0:720, :]
                weights[j] = index_to_weight[i]
                j += 1
            air_temperature = aggregate_images(images, weights=weights)

        return {VAR_NAME: air_temperature}

    def _get_file_and_time_index(self, i):
        return self.source_time_ranges[i][2:4]

    def get_source_time_ranges(self):
        return self.source_time_ranges

    def get_spatial_coverage(self):
        return 0, 0, 1440, 720

    def close(self):
        self.dataset_cache.close_all_datasets()

    def _init_source_time_ranges(self):
        source_time_ranges = []
        file_names = os.listdir(self.dir_path)
        for file_name in file_names:
            source_year = int(file_name.replace('.nc', '').split('_', 1)[1])
            if self.cube_config.start_time.year <= source_year <= self.cube_config.end_time.year:
                file = os.path.join(self.dir_path, file_name)
                dataset = self.dataset_cache.get_dataset(file)
                times = dataset.variables['time']
                dates = netCDF4.num2date(times[:], 'hours since 1900-01-01 00:00:0.0', calendar='gregorian')
                self.dataset_cache.close_dataset(file)
                source_time_ranges += [(dates[i], dates[i] + timedelta(hours=6), file, i) for i in range(len(dates))]
        self.source_time_ranges = sorted(source_time_ranges, key=lambda item: item[0])