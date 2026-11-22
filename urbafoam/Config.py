"""Typed urbafoam.toml configuration.

All settings and their defaults live here. `setup` writes the fully resolved configuration back
to `<case>/urbafoam.toml` (keeping the user's comments), so every setting is visible and editable.

Files from earlier versions (sections like ``["urbafoam.wind"]``) are migrated when loaded.
"""
import os
from pathlib import Path
from typing import Annotated, Literal

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .DataIO import normalise_format
from .Enums import Quality, modelTypeLookup, turbulenceTypeLookup

CONFIG_FILE = "urbafoam.toml"

# Keep ints as ints (e.g. `cell_size = 10` renders as 10, not 10.0, in the OpenFOAM files).
Number = int | float


class Section(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)


class WindConfig(Section):
    wind_directions: list[Number] = [270]


class ModelsConfig(Section):
    primary_buildings: str | None = None
    surrounding_buildings: str | None = None
    height_attribute: str = "height"
    # Translation applied to the models before meshing; results are moved back to model coordinates.
    # 'auto' puts the base of the primary model at z = 0 and, for models in map coordinates (more
    # than 10 km from the origin), moves them next to the origin: STL stores 32 bit floats, which
    # only resolve 0.5 m at 5000 km.
    offset: Annotated[list[float], Field(min_length=3, max_length=3)] | Literal['auto'] = 'auto'
    # Smallest building detail the mesh resolves, in m. Footprint gaps narrower than half of it are
    # closed, outlines simplified and smaller courtyards and buildings removed. 'auto' uses the finest
    # cell size near the primary buildings (e.g. 0.625 m for quick), 0 turns the clean-up off.
    min_feature_size: Annotated[float, Field(ge=0)] | Literal['auto'] = 'auto'
    # Surrounding buildings further than this from the primary model (in m) are left out. 'auto' keeps
    # those within (inlet_buffer - 1) primary building heights, so they stay clear of the inlet.
    surrounding_radius: Annotated[float, Field(gt=0)] | Literal['auto'] = 'auto'
    crs: str | None = None


class ParallelConfig(Section):
    procs: int = Field(default_factory=lambda: max(1, (os.cpu_count() or 2) // 2), ge=1)


class PostprocessConfig(Section):
    sampleBuffer: Number = 10
    sampleSpacing: Number = Field(default=1.0, gt=0)
    sampleHeights: list[Number] = [2, 10]
    samplePoints: str | None = None
    calcSpeedup: bool = True
    scaleVectorsBy: Number = 2.0
    outputFormat: str = 'csv'

    @field_validator('outputFormat')
    @classmethod
    def _known_format(cls, value):
        return normalise_format(value)


class InitialConditionsConfig(Section):
    z0: str | float = 'urban'  # terrain type name or roughness length in m
    turbulenceModel: str
    Uref: Number = 10
    Href: Number = 30

    @field_validator('z0')
    @classmethod
    def _known_terrain(cls, value):
        if isinstance(value, str):
            value = value.lower()
            if value not in modelTypeLookup:
                raise ValueError(f"terrain type '{value}' not recognised, use one of {list(modelTypeLookup)} "
                                 "or a roughness length in m")
        return value

    @field_validator('turbulenceModel')
    @classmethod
    def _known_turbulence_model(cls, value):
        if value.lower() not in turbulenceTypeLookup:
            raise ValueError(f"'{value}' is not a supported turbulence model, use 'KE' or 'KOmegaSST'")
        return value


class WindtunnelConfig(Section):
    cell_size: Number = 10
    z_grading: Number = 2
    # domain extents in multiples of the tallest building height
    inlet_buffer: Number  # upstream of the model
    outlet_buffer: Number  # downstream of the model
    height_buffer: Number
    side_buffer: Number = 5


class SnappyConfig(Section):
    verticalDomainRefinement: int
    CentralRefinement: int
    verticalCentralRefinement: list[int] = Field(min_length=2, max_length=2)
    CellsBetweenLevels: int
    addLayers: bool = False
    SurfaceLayers: int = Field(ge=0)
    IncludeAngle: Number = 150
    resolveFeatureAngle: Annotated[Number, Field(ge=0, le=180)] = 30
    PrimaryFeatureLevel: int
    SurroundingFeatureLevel: int
    PrimaryModelRefinementLevel: str
    SurroundingModelRefinementLevel: str
    # snappyHexMesh stops refining, part way through a level, when the mesh reaches this size
    maxGlobalCells: int = Field(default=20_000_000, gt=0)


class ControlsConfig(Section):
    endTime: Number
    deltaT: Number
    writeInterval: Number
    purgeWrite: int = 1


class SchemeConfig(Section):
    gradLimit_U: Number = 1
    gradLimit_p: Number = 1
    gradLimit_k: Number = 1
    gradLimit_eps: Number = 1
    gradLimit_omega: Number = 1


class DebugConfig(Section):
    write_postProcess: bool = False


QUALITY_DEFAULTS = {
    'quick': {
        'initial_conditions': {'turbulenceModel': 'KE'},
        'windtunnel': {'inlet_buffer': 4, 'outlet_buffer': 8, 'height_buffer': 3},
        'snappy': {
            'verticalDomainRefinement': 1, 'CentralRefinement': 2, 'verticalCentralRefinement': [4, 3],
            'CellsBetweenLevels': 2, 'SurfaceLayers': 2,
            'PrimaryFeatureLevel': 4, 'SurroundingFeatureLevel': 3,
            'PrimaryModelRefinementLevel': '(2 4)', 'SurroundingModelRefinementLevel': '(2 2)',
        },
        'controls': {'endTime': 800, 'deltaT': 2, 'writeInterval': 100},
    },
    'normal': {
        'initial_conditions': {'turbulenceModel': 'KOmegaSST'},
        'windtunnel': {'inlet_buffer': 6, 'outlet_buffer': 12, 'height_buffer': 6},
        'snappy': {
            'verticalDomainRefinement': 2, 'CentralRefinement': 3, 'verticalCentralRefinement': [5, 3],
            'CellsBetweenLevels': 3, 'SurfaceLayers': 3,
            'PrimaryFeatureLevel': 5, 'SurroundingFeatureLevel': 3,
            'PrimaryModelRefinementLevel': '(3 3)', 'SurroundingModelRefinementLevel': '(2 3)',
        },
        'controls': {'endTime': 1200, 'deltaT': 1, 'writeInterval': 400},
    },
}

_QUALITY_ALIASES = {'q': 'quick', 'quick': 'quick', 'n': 'normal', 'normal': 'normal'}


def normalise_quality(value):
    quality = _QUALITY_ALIASES.get(str(value).lower())
    if quality is None:
        raise ValueError(f"unknown quality '{value}', must be either '(q)uick' or '(n)ormal'")
    return quality


class UrbafoamConfig(Section):
    quality: Literal['quick', 'normal'] = 'quick'
    wind: WindConfig = Field(default_factory=WindConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    postprocess: PostprocessConfig = Field(default_factory=PostprocessConfig)
    initial_conditions: InitialConditionsConfig
    windtunnel: WindtunnelConfig
    snappy: SnappyConfig
    controls: ControlsConfig
    scheme: SchemeConfig = Field(default_factory=SchemeConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)

    @model_validator(mode='before')
    @classmethod
    def _apply_quality_defaults(cls, data):
        data = dict(data)
        quality = normalise_quality(data.get('quality', 'quick'))
        data['quality'] = quality
        for section, defaults in QUALITY_DEFAULTS[quality].items():
            data[section] = {**defaults, **(data.get(section) or {})}
        return data

    @property
    def quality_level(self):
        return Quality.NORMAL if self.quality == 'normal' else Quality.QUICK


# ----------------------------------------------------------------------------------------------
# reading / writing

_LEGACY_SECTIONS = {
    'urbafoam.wind': 'wind',
    'urbafoam.models': 'models',
    'urbafoam.parallel': 'parallel',
    'urbafoam.postprocess': 'postprocess',
    'urbafoam.initalconditions': 'initial_conditions',
    'urbafoam.windtunnel': 'windtunnel',
    'urbafoam.snappy': 'snappy',
    'urbafoam.controls': 'controls',
    'urbafoam.scheme': 'scheme',
    'urbafoam.debug': 'debug',
}
# the old names had upstream and downstream swapped: 'downwind_buffer' set the inlet (upstream) length
_LEGACY_KEYS = {'windtunnel': {'downwind_buffer': 'inlet_buffer', 'upwind_buffer': 'outlet_buffer'}}


def _move(container, old, new):
    item = container[old]
    del container[old]
    container[new] = item


def _migrate_legacy(doc):
    """Rewrite a config document from an earlier version in place to the current layout (comments are kept)."""
    if 'urbafoam' in doc:  # [urbafoam.wind] written without quotes parses as a nested table
        nested = doc['urbafoam']
        del doc['urbafoam']
        for name in list(nested.keys()):
            doc[f'urbafoam.{name}'] = nested[name]
    for key in list(doc.keys()):
        new = _LEGACY_SECTIONS.get(key.lower())
        if new is not None:
            _move(doc, key, new)
    for section, renames in _LEGACY_KEYS.items():
        if section in doc:
            for old, new in renames.items():
                if old in doc[section] and new not in doc[section]:
                    _move(doc[section], old, new)
    doc.pop('out_dir', None)  # the case directory always comes from the command line
    return doc


def read_document(config_file=None, case_dir=None):
    """Read `config_file`, or `<case_dir>/urbafoam.toml` if it exists, as a (migrated) tomlkit document."""
    if config_file is None and case_dir is not None and (Path(case_dir) / CONFIG_FILE).is_file():
        config_file = Path(case_dir) / CONFIG_FILE
    if config_file is None:
        return tomlkit.document()
    with open(config_file) as src:
        return _migrate_legacy(tomlkit.load(src))


class ConfigError(ValueError):
    pass


def build_config(doc, quality=None):
    """Validate a config document. If `quality` changes the quality level, settings that still have
    the previous level's default value switch to the new level's default; edited values are kept."""
    data = doc.unwrap()
    try:
        if quality is not None:
            old, new = normalise_quality(data.get('quality', 'quick')), normalise_quality(quality)
            if old != new:
                for section, defaults in QUALITY_DEFAULTS[old].items():
                    values = data.get(section, {})
                    for key, default in defaults.items():
                        if values.get(key) == default:
                            del values[key]
            data['quality'] = new
        return UrbafoamConfig.model_validate(data)
    except (ValidationError, ValueError) as e:
        raise ConfigError(f"invalid urbafoam configuration:\n{e}") from e


def load_config(config_file=None, case_dir=None, quality=None):
    """Return (validated config, tomlkit document to save it back into)."""
    doc = read_document(config_file, case_dir)
    return build_config(doc, quality), doc


def _unwrap(item):
    return item.unwrap() if hasattr(item, 'unwrap') else item  # tomlkit returns bools as plain bool


def _update(container, data):
    for key in list(container.keys()):
        if key not in data:
            del container[key]
    for key, value in data.items():
        if isinstance(value, dict):
            if key not in container or not isinstance(container[key], dict):
                container[key] = tomlkit.table()
            _update(container[key], value)
        elif key not in container or _unwrap(container[key]) != value:
            container[key] = value


def save_config(config, case_dir, doc=None):
    """Write the resolved config to `<case_dir>/urbafoam.toml`, keeping comments from `doc`."""
    doc = doc if doc is not None else tomlkit.document()
    _update(doc, config.model_dump(mode='json', exclude_none=True))
    with open(Path(case_dir) / CONFIG_FILE, 'w') as dst:
        tomlkit.dump(doc, dst)
