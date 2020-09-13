from . import ModelType
from .windProfile import turbulenceConstants

def setup_initial_conditions(model_type,bounds):
    refSpeed = 6
    Href = 30
    Zref = 10
    z0ref = 0.1

    if model_type == ModelType.DENSE_URBAN:
        ABL = 420
        z0 = 1.5
    if model_type == ModelType.URBAN:
        ABL = 420
        z0 = 1
    elif model_type == ModelType.SUBURB or model_type == ModelType.FOREST:
        ABL = 320
        z0 = 0.8
    elif model_type == ModelType.PARK:
        ABL = 320
        z0 = 0.5
    elif model_type == ModelType.FIELD:
        ABL = 320
        z0 = 0.05
    elif model_type == ModelType.WATER:
        ABL = 320
        z0 = 0.005

    zBlend = min(ABL, bounds[2][1] * 10)

    ke, eps = turbulenceConstants(Href, z0, refSpeed, Zref, z0ref)

    initial_conditions = {
        'turbulentKE': ke,
        'turbulentEpsilon': eps,
        'Uref': refSpeed,
        'refSpeed': refSpeed,
        'Href': Href,
        'z0': z0,
    }
    return initial_conditions