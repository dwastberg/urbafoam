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
    'dense_urban': ModelType.URBAN,
    'urban': ModelType.URBAN,
    'suburb': ModelType.SUBURB,
    'suburban': ModelType.SUBURB,
    'forset': ModelType.FOREST,
    'park': ModelType.PARK,
    'field': ModelType.FIELD,
    'water':ModelType.WATER
}