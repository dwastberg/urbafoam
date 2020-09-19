import toml
from pathlib import Path


def load_config(config_file, out_dir):
    out_dir = Path(out_dir)
    config = {}
    if config_file is None:
        if (out_dir / "urbafoam.toml").is_file():
            config_file = out_dir / "urbafoam.toml"
    if config_file is not None:
        with open(config_file) as src:
            config = toml.load(src)
    return config


def save_config_file(out_dir, config):
    with open(out_dir/'urbafoam.toml','w') as dst:
        toml.dump(config, dst)


def get_or_update_config(config, group, key, update_value, overwrite=False):
    group = group.lower()
    if group:
        if group not in config:
            config[group] = {}
        cfg_group = config[group]
    else:
        cfg_group = config
    value = cfg_group.get(key,None)
    if value is None or overwrite is True:
        cfg_group[key]=update_value
    return cfg_group[key]


