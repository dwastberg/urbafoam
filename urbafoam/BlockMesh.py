from math import ceil

from ofblockmeshdicthelper import BlockMeshDict, SimpleGrading

from .Config import get_or_update_config
from .Enums import Quality


def setup_windtunnel(config, primary_bounds, quality, case_dir, minZ=None):
    config_group = "urbafoam.windtunnel"
    cell_size = get_or_update_config(config, config_group, "cell_size", 10)
    z_grading = get_or_update_config(config, config_group, "z_grading", 2)
    min_x = primary_bounds[0][0]
    max_x = primary_bounds[0][1]
    min_y = primary_bounds[1][0]
    max_y = primary_bounds[1][1]
    min_z = primary_bounds[2][0]
    max_z = primary_bounds[2][1]
    if minZ is not None:
        min_z = minZ
    if quality == Quality.QUICK:
        inlet_buffer = max_z * 4
        outflow_buffer = max_z * 8
        height_factor = 3
    elif quality == Quality.NORMAL:
        inlet_buffer = max_z * 6
        outflow_buffer = max_z * 12
        height_factor = 6

    side_buffer = max_z * 5
    model_width = max_y - min_y
    min_domain_width = model_width / 0.17  # 17% is recommended minimal value in Blocken
    if quality == Quality.QUICK:
        side_buffer = min((min_domain_width - model_width) / 2, side_buffer)
    if quality == Quality.NORMAL:
        side_buffer = max((min_domain_width - model_width) / 2, side_buffer)
    background_minx = min_x - inlet_buffer
    background_maxx = max_x + outflow_buffer
    background_miny = min_y - side_buffer
    background_maxy = max_y + side_buffer
    background_minz = min_z
    background_maxz = max_z * height_factor

    x_range = background_maxx - background_minx
    y_range = background_maxy - background_miny
    z_range = background_maxz - background_minz

    x_cells = int(ceil(x_range / cell_size))
    y_cells = int(ceil(y_range / cell_size))
    z_cells = int(ceil(z_range / cell_size))

    blockmesh_domain = build_windtunnel(background_minx, background_maxx, background_miny, background_maxy,
                                        background_minz,
                                        background_maxz, x_cells, y_cells, z_cells, z_grading)

    write_bmd(blockmesh_domain, case_dir)
    windtunnel_data = {}
    windtunnel_data['cell_size'] = cell_size
    windtunnel_data['background_minx'] = background_minx
    windtunnel_data['background_miny'] = background_miny
    windtunnel_data['background_minz'] = background_minz
    windtunnel_data['background_maxx'] = background_maxx
    windtunnel_data['background_maxy'] = background_maxy
    windtunnel_data['background_maxz'] = background_maxz
    windtunnel_data['zGround'] = background_minz

    return windtunnel_data


def build_windtunnel(xMin, xMax, yMin, yMax, zMin, zMax, xCells, yCells, zCells, zGrading=1):
    bmd = BlockMeshDict()

    bmd.add_vertex(xMin, yMin, zMin, 'd0')
    bmd.add_vertex(xMax, yMin, zMin, 'd1')
    bmd.add_vertex(xMax, yMax, zMin, 'd2')
    bmd.add_vertex(xMin, yMax, zMin, 'd3')

    bmd.add_vertex(xMin, yMin, zMax, 'd4')
    bmd.add_vertex(xMax, yMin, zMax, 'd5')
    bmd.add_vertex(xMax, yMax, zMax, 'd6')
    bmd.add_vertex(xMin, yMax, zMax, 'd7')

    backgroundMesh = bmd.add_hexblock(('d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7'), (xCells, yCells, zCells),
                                      'background', SimpleGrading(1, 1, zGrading))

    bmd.add_boundary('patch', 'inlet', [backgroundMesh.face('xm')])
    bmd.add_boundary('patch', 'outlet', [backgroundMesh.face('xp')])
    bmd.add_boundary('wall', 'ground', [backgroundMesh.face('zm')])
    bmd.add_boundary('symmetry', 'frontAndBack',
                     [backgroundMesh.face('ym'), backgroundMesh.face('yp'), backgroundMesh.face('zp')])
    return bmd


def write_bmd(bmd, case_dir, suffix=''):
    bmd.assign_vertexid()
    out_file = case_dir / 'constant' / 'polyMesh' / ('blockMeshDict' + suffix)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, 'w') as dst:
        dst.write(bmd.format())
