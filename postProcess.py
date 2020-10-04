from pathlib import Path

from urbafoam.Config import load_config, get_value, get_or_update_config
from urbafoam.PostProcess import write_oriented_data, find_sample_points_with_data, normalize_oriented_data, orient_sample_date
from urbafoam.DataIO import writeWindPoints, writeWindVectors

if __name__ == '__main__':
    import argparse


    parser = argparse.ArgumentParser()
    parser.add_argument('--case-dir')
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    case_dir = case_dir.expanduser()
    config = load_config(case_dir / 'urbafoam.toml')
    wind_directions = get_value(config, "urbafoam.wind", "wind_direction")
    sample_spacing = get_value(config, "urbafoam.postprocess", "sampleSpacing")
    WRITE = get_or_update_config(config,"urbafoam.debug","write_postProcess", True)

    if WRITE:
        for w in wind_directions:
            write_oriented_data(case_dir / str(w), 'samplePoints_2m')
    sample_points_with_data = find_sample_points_with_data(case_dir, 'samplePoints_2m', sample_spacing, wind_directions,
                                                           write=WRITE)
    base_points, normalized_data = normalize_oriented_data(sample_points_with_data, case_dir, wind_directions,
                                                           'samplePoints_2m')
    writeWindPoints(base_points,normalized_data,wind_directions,case_dir/'wind_U_pts.shp',format='shp')
    for w in wind_directions:
        data = orient_sample_date(case_dir/str(w), 'samplePoints_2m', field='U')
        writeWindVectors(data,case_dir/f"windVectors_{w}.shp",format='shp')



