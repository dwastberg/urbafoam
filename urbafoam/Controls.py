def setup_controls(controls_cfg):
    return {
        'application': 'simpleFoam',
        'startFrom': 'latestTime',
        'endTime': controls_cfg.endTime,
        'deltaT': controls_cfg.deltaT,
        'writeInterval': controls_cfg.writeInterval,
        'purgeWrite': controls_cfg.purgeWrite,
        'controlFunctions': [],
    }
