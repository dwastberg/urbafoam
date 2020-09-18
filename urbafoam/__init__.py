__version__ = "0.1.0"

from pathlib import Path
import os, stat
from enum import Enum, auto
import pystache
from pystache.common import MissingTags

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

from .Mesh import Mesh
from .BlockMesh import setup_windtunnel
from .SnappyHexMesh import setup_snappy
from .Controls import setup_controls
from .InitialConditions import setup_initial_conditions
from .Scheme import setup_scheme
from .SamplePoints import setup_samplepoint

def main(building_model,wind_directions,quality, procs, out_dir):
    buildingMesh = Mesh()
    buildingMesh.load_mesh(building_model)
    out_dir = Path(out_dir).expanduser()
    for w in wind_directions:
        case_dir = out_dir/ str(w)
        buildingMesh.rotate_and_save_mesh(w,case_dir)

        windtunnel_data = setup_windtunnel(buildingMesh.rotated_bounds,quality,case_dir,8,0)
        snappy_data = setup_snappy(windtunnel_data,[buildingMesh],quality)
        control_data = setup_controls(quality)
        initial_condition = setup_initial_conditions(ModelType.URBAN,buildingMesh.rotated_bounds)
        scheme_data = setup_scheme()

        sample_point_data = setup_samplepoint(buildingMesh.rotated_mesh, 2, [2,10])


        case_data = {**windtunnel_data,
                     **snappy_data,
                     **control_data,
                     **initial_condition,
                     **scheme_data,
                     **sample_point_data}

        if quality == Quality.QUICK:
            case_data['usePotentialFoam'] = True
        else:
            case_data['usePotentialFoam'] = False

        case_data['procCount'] = procs
        case_data['eachCaseParallel'] = procs > 1

        write_case_files(case_data,case_dir)
    create_run_all_cases_script(out_dir,wind_directions)

def write_case_files(case_data,case_dir):
    template_dir = Path(__file__).parent / 'templates'
    case_files = [x for x in template_dir.glob('**/*') if x.is_file() and x.name[0] != '_']
    for c in case_files:
        with open(c, 'r') as src:
            content = src.read()
        content = pystache.render(content, case_data, missing_tags=MissingTags.strict)
        output_file = case_dir / c.relative_to(template_dir)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', newline='\n') as dst:
            dst.write(content)
        if content.strip().startswith('#!'):
            st = os.stat(output_file)
            os.chmod(output_file, 0o755)


def create_run_all_cases_script(out_dir,wind_directions):
    out_dir = Path(out_dir)
    out_string = "#!/bin/sh\n\n"

    for n,w in enumerate(wind_directions):
        out_string+=f"{str(w)}/Allrun;\n"

    with open(out_dir/"RunAllCases", 'w', newline='\n') as f:
        f.write(out_string)
