from pathlib import Path

from urbafoam.Config import load_config, get_value
from urbafoam.PostProcess import write_oriented_data, find_used_sample_points, normalize_oriented_data

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--case-dir')
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    case_dir = case_dir.expanduser()
    config = load_config(case_dir / 'urbafoam.toml')
    wind_directions = get_value(config, "urbafoam.wind", "wind_direction")

    for w in wind_directions:
        write_oriented_data(case_dir / str(w), 'samplePoints_2m')
    find_used_sample_points(case_dir, 'samplePoints_2m', 1, wind_directions)
    normalize_oriented_data(case_dir, wind_directions, 'samplePoints_2m')
