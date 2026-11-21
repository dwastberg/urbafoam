from enum import Enum, auto


class MeshTypes(Enum):
    PRIMARY = auto()
    SURROUNDING = auto()
    TERRAIN = auto()


class Quality(Enum):
    QUICK = auto()
    NORMAL = auto()


class ModelType(Enum):
    DENSE_URBAN = auto()
    URBAN = auto()
    SUBURB = auto()
    FOREST = auto()
    PARK = auto()
    FIELD = auto()
    WATER = auto()

modelTypeLookup = {
    'dense': ModelType.DENSE_URBAN,
    'denseurban': ModelType.DENSE_URBAN,
    'dense_urban': ModelType.DENSE_URBAN,
    'urban': ModelType.URBAN,
    'suburb': ModelType.SUBURB,
    'suburban': ModelType.SUBURB,
    'forest': ModelType.FOREST,
    'forset': ModelType.FOREST,  # misspelling accepted by earlier versions
    'park': ModelType.PARK,
    'field': ModelType.FIELD,
    'water':ModelType.WATER
}

class TurbulenceModels(Enum):
    KEpsilon = auto()
    KOmegaSST = auto()

turbulenceTypeLookup = {
    'ke': TurbulenceModels.KEpsilon,
    'k_e': TurbulenceModels.KEpsilon,
    'kepsilon': TurbulenceModels.KEpsilon,
    'ko': TurbulenceModels.KOmegaSST,
    'k_o': TurbulenceModels.KOmegaSST,
    'komega': TurbulenceModels.KOmegaSST,
    'komegasst': TurbulenceModels.KOmegaSST,

}