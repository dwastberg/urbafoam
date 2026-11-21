from .Enums import ModelType, TurbulenceModels, modelTypeLookup, turbulenceTypeLookup
from .windProfile import turbulenceConstants

# aerodynamic roughness length z0 [m] per terrain type
ROUGHNESS_LENGTH = {
    ModelType.DENSE_URBAN: 1.5,
    ModelType.URBAN: 1.0,
    ModelType.SUBURB: 0.8,
    ModelType.FOREST: 0.8,
    ModelType.PARK: 0.5,
    ModelType.FIELD: 0.05,
    ModelType.WATER: 0.005,
}


def setup_initial_conditions(ic_cfg):
    refSpeed = ic_cfg.Uref
    Href = ic_cfg.Href

    if isinstance(ic_cfg.z0, str):
        z0 = ROUGHNESS_LENGTH[modelTypeLookup[ic_cfg.z0]]
    else:
        z0 = float(ic_cfg.z0)
    turbModel = turbulenceTypeLookup[ic_cfg.turbulenceModel.lower()]

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
        'Href': Href,
        'z0': z0,
        'z0_walls': z0_walls,
        'z0_other': z0_other
    }
    return initial_conditions
