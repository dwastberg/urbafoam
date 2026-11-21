from math import ceil

from .Enums import Quality


def setup_windtunnel(windtunnel_cfg, quality, primary_bounds, surrounding_bounds, minZ=None):
    cell_size = windtunnel_cfg.cell_size
    z_grading = windtunnel_cfg.z_grading
    min_x = primary_bounds[0][0]
    max_x = primary_bounds[0][1]
    min_y = min(primary_bounds[1][0],surrounding_bounds[1][0])
    max_y = max(primary_bounds[1][1],surrounding_bounds[1][1])
    min_z = primary_bounds[2][0]
    max_z = max(primary_bounds[2][1],surrounding_bounds[2][1])
    if minZ is not None:
        min_z = minZ
    inlet_buffer = max_z * windtunnel_cfg.inlet_buffer
    outflow_buffer = max_z * windtunnel_cfg.outlet_buffer
    height_factor = windtunnel_cfg.height_buffer
    side_buffer = max_z * windtunnel_cfg.side_buffer
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

    windtunnel_data = {}
    # written to system/caseParameters, which system/blockMeshDict reads
    windtunnel_data['x_cells'] = int(ceil(x_range / cell_size))
    windtunnel_data['y_cells'] = int(ceil(y_range / cell_size))
    windtunnel_data['z_cells'] = int(ceil(z_range / cell_size))
    windtunnel_data['z_grading'] = z_grading
    windtunnel_data['cell_size'] = cell_size
    windtunnel_data['background_minx'] = background_minx
    windtunnel_data['background_miny'] = background_miny
    windtunnel_data['background_minz'] = background_minz
    windtunnel_data['background_maxx'] = background_maxx
    windtunnel_data['background_maxy'] = background_maxy
    windtunnel_data['background_maxz'] = background_maxz

    return windtunnel_data

