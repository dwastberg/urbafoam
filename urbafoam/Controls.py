from . import Quality
from .Config import get_or_update_config


def setup_controls(config, quality):
    config_group = "urbafoam.controls"
    control_data = {}
    control_data['application'] = 'simpleFoam'
    control_data['startFrom'] = 'latestTime'

    if quality == Quality.QUICK:
        endTime = get_or_update_config(config, config_group, "endTime", 800)
        deltaT = get_or_update_config(config, config_group, "deltaT", 2)
        writeInterval = get_or_update_config(config, config_group, "writeInterval", 100)
    elif quality == Quality.NORMAL:
        endTime = get_or_update_config(config, config_group, "endTime", 1200)
        deltaT = get_or_update_config(config, config_group, "deltaT", 1)
        writeInterval = get_or_update_config(config, config_group, "writeInterval", 400)
    purgeWrite = get_or_update_config(config, config_group, "purgeWrite", 1)
    control_data['endTime'] = endTime
    control_data['deltaT'] = deltaT
    control_data['writeInterval'] = writeInterval
    control_data['purgeWrite'] = purgeWrite
    control_data['controlFunctions'] = []
    return control_data
