import sys, os

from urbafoam import main, Quality


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--wind-directions',
                        help='wind directions to simulate as comma separated numbers. Default is 270 degress')
    parser.add_argument('--building-model')
    parser.add_argument('--quality', default='quick', help='Quality of the simulation, currently supports (q)uick or (n)ormal. Default quick')
    parser.add_argument('-p', default=1, type=int, help='Number of cores to use')
    parser.add_argument('--out-dir')

    args = parser.parse_args()

    if args.wind_directions is not None:
        wind_directions = args.wind_directions.split(',')
        try:
            wind_directions = [float(w.strip()) for w in wind_directions]
        except:
            print("failed to parse wind directions", args.wind_directons)
            sys.exit(1)
    else:
        wind_directions = [270]

    assert args.building_model is not None and os.path.isfile(args.building_model), "cannot find %s" % args.building_model

    if args.quality in ('normal','n','N','Normal'):
        quality = Quality.NORMAL
    elif args.quality in ('quick','q','Quick','Q'):
        quality = Quality.QUICK

    if args.out_dir is None:
        print("Must set an output directory")
        sys.exit(1)

    main(args.building_model,wind_directions, quality, args.p, args.out_dir)


