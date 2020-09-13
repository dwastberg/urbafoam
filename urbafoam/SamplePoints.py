from shapely.geometry import MultiPoint, mapping
import numpy as np


def setup_samplepoint(central_mesh, spacing, heights, buffering=10):
    sample_points = generate_sample_points(central_mesh, spacing, buffering)
    sample_data = {'runSample': True,
                   'pointClouds': []}
    for h in heights:
        name = f'samplePoints_{h}m'
        pts_string = point_array_to_sample_format(sample_points + h)
        sample_data['pointClouds'].append({'name': name, 'samplePoints': pts_string})
    return sample_data


def generate_sample_points(central_mesh, spacing, buffering=10):
    projected_mesh_points = MultiPoint(list(zip(central_mesh.x.flatten(), central_mesh.y.flatten())))
    central_hull = projected_mesh_points.convex_hull
    central_hull = central_hull.buffer(buffering)
    central_bound = central_hull.bounds
    x = np.arange(central_bound[0] - spacing, central_bound[2] + spacing, spacing)
    y = np.arange(central_bound[1] - spacing, central_bound[3] + spacing, spacing)
    pts = np.dstack(np.meshgrid(x, y)).reshape(-1, 2)
    pts = np.hstack((pts, np.zeros((pts.shape[0], 1))))
    pts = MultiPoint(pts)
    pts = pts.intersection(central_hull)
    pts = np.array(mapping(pts)['coordinates'])

    return pts


def point_array_to_sample_format(samplePoints):
    sampleText = '(\n'
    samplePoints_str = []
    for pt in samplePoints:
        samplePoints_str.append(f'({pt[0]} {pt[1]} {pt[2]})')
    sampleText += '\n'.join(samplePoints_str)
    sampleText += ');\n'
    return sampleText
