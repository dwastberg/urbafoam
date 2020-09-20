from urbafoam.PostProcess import write_oriented_data
from urbafoam.Config import load_config, get_value
from pathlib import Path

if __name__=='__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--case-dir')
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    case_dir = case_dir.expanduser()
    config = load_config(case_dir/'urbafoam.toml')
    wind_directions = get_value(config,"urbafoam.wind","wind_direction")

    for w in wind_directions:
        write_oriented_data(case_dir/str(w),'samplePoints_2m')


