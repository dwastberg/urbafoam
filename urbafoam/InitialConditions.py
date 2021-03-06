from .Config import get_or_update_config
from .Enums import ModelType, TurbulenceModels
from .windProfile import turbulenceConstants


def setup_initial_conditions(config, surroundings, turbModel, bounds):
    config_group = "urbafoam.initalConditions"
    refSpeed = get_or_update_config(config, config_group, "Uref", 10)
    Href = get_or_update_config(config, config_group, "Href", 30)

    if isinstance(surroundings,float):
        z0 = surroundings
        if z0>=1:
            ABL = 420
        else:
            ABL = 320
    else:
        if surroundings == ModelType.DENSE_URBAN:
            ABL = 420
            z0 = 1.5
        elif surroundings == ModelType.URBAN:
            ABL = 420
            z0 = 1.0
        elif surroundings == ModelType.SUBURB or surroundings == ModelType.FOREST:
            ABL = 320
            z0 = 0.8
        elif surroundings == ModelType.PARK:
            ABL = 320
            z0 = 0.5
        elif surroundings == ModelType.FIELD:
            ABL = 320
            z0 = 0.05
        elif surroundings == ModelType.WATER:
            ABL = 320
            z0 = 0.005

    zBlend = min(ABL, bounds[2][1] * 10)
    z0_walls = 0.001
    z0_other = 0.001
    ke, eps, omega = turbulenceConstants(Href, z0, refSpeed)

    if turbModel == TurbulenceModels.KOmegaSST:
        turbulenceModel = 'kOmegaSST'
    else:
        turbulenceModel = 'kEpsilon'

    initial_conditions = {
        'turbulenceModel': turbulenceModel,
        'turbulentKE': ke,
        'turbulentEpsilon': eps,
        'turbulentOmega': omega,
        'Uref': refSpeed,
        'refSpeed': refSpeed,
        'Href': Href,
        'z0': z0,
        'z0_walls': z0_walls,
        'z0_other': z0_other
    }
    return initial_conditions
