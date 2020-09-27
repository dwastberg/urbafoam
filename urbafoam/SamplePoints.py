import numpy as np
from shapely.geometry import MultiPoint, mapping


def setup_samplepoint(sample_points, rotation_matrix, centerpoint, heights):
    rotated_points = (sample_points - centerpoint).dot(rotation_matrix) + centerpoint
    sample_data = {'runSample': True,
                   'pointClouds': []}
    for h in heights:
        name = f'samplePoints_{h}m'
        pts_string = point_array_to_sample_format(rotated_points + h)
        sample_data['pointClouds'].append({'name': name, 'samplePoints': pts_string})
    return sample_data


def generate_sample_points(sample_area, spacing):
    sample_bound = sample_area.bounds
    x = np.arange(sample_bound[0] - spacing, sample_bound[2] + spacing, spacing)
    y = np.arange(sample_bound[1] - spacing, sample_bound[3] + spacing, spacing)
    pts = np.dstack(np.meshgrid(x, y)).reshape(-1, 2)
    pts = np.hstack((pts, np.zeros((pts.shape[0], 1))))
    pts = MultiPoint(pts)
    pts = pts.intersection(sample_area)
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


