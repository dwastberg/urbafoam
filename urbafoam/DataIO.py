import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from .Paths import case_dir_name

# output format name -> (file extension, GDAL driver); csv is written without a driver
OUTPUT_FORMATS = {
    'csv': ('csv', None),
    'json': ('json', 'GeoJSON'),
    'geojson': ('json', 'GeoJSON'),
    'shp': ('shp', 'ESRI Shapefile'),
    'shape': ('shp', 'ESRI Shapefile'),
    'gpkg': ('gpkg', 'GPKG'),
}


def normalise_format(format):
    format = format.replace('.', '').lower()
    if format not in OUTPUT_FORMATS:
        raise ValueError(f'output type {format} not recognized. Must be one of {tuple(OUTPUT_FORMATS)}')
    return format


def output_extension(format):
    return OUTPUT_FORMATS[normalise_format(format)][0]


def _write_gis(gdf, out_file, format):
    gdf.to_file(out_file, driver=OUTPUT_FORMATS[format][1], engine='pyogrio')


def writeWindPoints(basepoints, data, wind_dirs, out_file, format='csv', offset=None, crs=None):
    format = normalise_format(format)
    basepoints = np.asarray(basepoints, dtype=float)
    if offset is not None:
        assert len(offset) == 3, "Offset must have a length of 3"
        basepoints = basepoints + np.asarray(offset, dtype=float)
    values = np.column_stack(data) if len(data) else np.empty((len(basepoints), 0))

    if format == 'csv':
        columns = {'X': basepoints[:, 0], 'Y': basepoints[:, 1], 'Z': basepoints[:, 2]}
        columns.update({f'wind_dir{case_dir_name(w)}': values[:, i] for i, w in enumerate(wind_dirs)})
        pd.DataFrame(columns).to_csv(out_file, index=False)
    else:
        # GIS attribute names are kept short for the 10 character shapefile limit
        properties = {f'w_dir{case_dir_name(w)}': values[:, i] for i, w in enumerate(wind_dirs)}
        geometry = shapely.points(basepoints)
        _write_gis(gpd.GeoDataFrame(properties, geometry=geometry, crs=crs), out_file, format)


def writeWindVectors(data, out_file, scale=1.0, format='csv', offset=None, crs=None):
    format = normalise_format(format)
    data = np.array(data, dtype=float)  # copy: the caller's array is left untouched
    if offset is not None:
        assert len(offset) == 3, "Offset must have a length of 3"
        offset = np.array(offset)
        data[:, :3] += offset  # start points
        data[:, 3:6] += offset  # end points

    if scale != 1:
        start_point, end_point = data[:, :3], data[:, 3:6]
        data[:, 3:6] = start_point + (end_point - start_point) * scale

    if format == 'csv':
        header = "start_X,start_Y,start_Z,end_X,end_Y,end_Z,speedup"
        np.savetxt(out_file, data, delimiter=',', header=header, comments='')
    else:
        geometry = shapely.linestrings(data[:, :6].reshape(-1, 2, 3))
        _write_gis(gpd.GeoDataFrame({'speedup': data[:, 6]}, geometry=geometry, crs=crs), out_file, format)
