import sys, os

from urbafoam import main, Quality
from urbafoam.Config import load_config, get_or_update_config


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--wind-directions',
                        help='wind directions to simulate as comma separated numbers. Default is 270 degress')
    parser.add_argument('--building-model')
    parser.add_argument('--quality',  help='Quality of the simulation, currently supports (q)uick or (n)ormal. Default quick')
    parser.add_argument('-p', type=int, help='Number of cores to use')
    parser.add_argument('--config', default=None)
    parser.add_argument('--out-dir')

    args = parser.parse_args()

    config = load_config(args.config,args.out_dir)

    if args.wind_directions is not None:
        wind_directions = args.wind_directions.split(',')
        try:
            wind_directions = [float(w.strip()) for w in wind_directions]
            get_or_update_config(config,"urbafoam.wind","wind_direction",wind_directions,True)
        except:
            print("failed to parse wind directions", args.wind_directons)
            sys.exit(1)
    else:
        wind_diriections = get_or_update_config(config, "urbafoam.wind", "wind_direction", [270])


    if args.building_model is None:
        primary_building_model = get_or_update_config(config, "urbafoam.models", "primaty_buildings", None)
    else:
        primary_building_model = get_or_update_config(config, "urbafoam.models", "primaty_buildings", args.building_model, True)


    assert primary_building_model is not None and os.path.isfile(primary_building_model), "cannot find building model %s" % args.building_model

    if args.quality is None:
        quality = get_or_update_config(config,"","quality",'quick')
    else:
        if args.quality in ('normal','n','N','Normal','quick','q','Quick','Q'):
            quality = get_or_update_config(config,"","quality",args.quality,overwrite=True)
        else:
            print(f"unknown quality {args.quality}, must be eithet '(q)uick' or '(n)ormal'")
            sys.exit(1)


    if quality in ('normal','n','N','Normal'):
        quality = Quality.NORMAL

    elif quality in ('quick','q','Quick','Q'):
        quality = Quality.QUICK

    if args.p is None:
        procs = get_or_update_config(config,"urbafoam.parallel","procs",os.cpu_count() // 2)
    else:
        procs = get_or_update_config(config, "urbafoam.parallel", "procs", args.p, overwrite=True)

    if args.out_dir is None:
        out_dir = get_or_update_config(config,"","out_dir",os.path.abspath(os.curdir))
    else:
        out_dir = get_or_update_config(config,"","out_dir",args.out_dir)


    main(primary_building_model,wind_directions, quality, procs, out_dir, config)


