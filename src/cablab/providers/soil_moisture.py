import os
from datetime import timedelta

import gridtools.resampling as gtr
import netCDF4
import numpy

from cablab import BaseCubeSourceProvider
from cablab.util import NetCDFDatasetCache, aggregate_images

VAR_NAME = 'SoilMoisture'
FILL_VALUE = -9999.0


class SoilMoistureProvider(BaseCubeSourceProvider):
    def __init__(self, cube_config, dir_path):
        super(SoilMoistureProvider, self).__init__(cube_config)
        self.dir_path = dir_path
        self.dataset_cache = NetCDFDatasetCache(VAR_NAME)
        self.source_time_ranges = None
        self.old_indices = None

    def prepare(self):
        self._init_source_time_ranges()

    def get_variable_descriptors(self):
        return {
            VAR_NAME: {
                'data_type': numpy.float32,
                'fill_value': FILL_VALUE,
                'units': 'm3',
                'long_name': 'Soil moisture',
                'scale_factor': 1.0,
                'add_offset': 0.0,
            }
        }

    def compute_variable_images_from_sources(self, index_to_weight):

        # close all datasets that wont be used anymore
        new_indices = set(index_to_weight.keys())
        if self.old_indices:
            unused_indices = self.old_indices - new_indices
            for i in unused_indices:
                file, _ = self._get_file_and_time_index(i)
                self.dataset_cache.close_dataset(file)
        self.old_indices = new_indices

        if len(new_indices) == 1:
            i = next(iter(new_indices))
            file, time_index = self._get_file_and_time_index(i)
            var_image = self.dataset_cache.get_dataset(file).variables[VAR_NAME][time_index, :, :]
        else:
            images = [None] * len(new_indices)
            weights = [None] * len(new_indices)
            j = 0
            for i in new_indices:
                file, time_index = self._get_file_and_time_index(i)
                images[j] = self.dataset_cache.get_dataset(file).variables[VAR_NAME][time_index, :, :]
                weights[j] = index_to_weight[i]
                j += 1
            var_image = aggregate_images(images, weights=weights)

        var_image = gtr.resample_2d(var_image, self.cube_config.grid_width, self.cube_config.grid_height,
                                    us_method=gtr.US_NEAREST, fill_value=FILL_VALUE)
        return {VAR_NAME: var_image}

    def _get_file_and_time_index(self, i):
        return self.source_time_ranges[i][2:4]

    def get_source_time_ranges(self):
        return self.source_time_ranges

    def get_spatial_coverage(self):
        return 0, 0, self.cube_config.grid_width, self.cube_config.grid_height

    def close(self):
        self.dataset_cache.close_all_datasets()

    def _init_source_time_ranges(self):
        source_time_ranges = []
        file_names = os.listdir(self.dir_path)
        for file_name in file_names:
            if file_name.endswith('.nc.gz'):
                file = os.path.join(self.dir_path, file_name)
                dataset = self.dataset_cache.get_dataset(file)
                time = dataset.variables['time']
                # dates = netCDF4.num2date(time[:], time.units, calendar=time.calendar)
                dates = netCDF4.num2date(time[:], 'days since 1582-10-15 00:00', calendar='gregorian')
                self.dataset_cache.close_dataset(file)
                n = len(dates)
                for i in range(n):
                    t1 = dates[i]
                    if i < n - 1:
                        t2 = dates[i + 1]
                    else:
                        t2 = t1 + timedelta(days=31)  # assuming it's December
                    source_time_ranges.append((t1, t2, file, i))
        self.source_time_ranges = sorted(source_time_ranges, key=lambda item: item[0])
