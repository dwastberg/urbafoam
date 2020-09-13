from . import Quality,MeshTypes
import os
def setup_snappy(windtunnel_data,building_models,quality):
    snappy_data = {}
    if quality == Quality.QUICK:
        verticalRefinementLevel = 2
        insideRefinementLevel = 2
        verticalCentralRefinement = '((3 4) (10 2))'
        nCellsBetweenLevels = 2
        nSurfaceLayers = 2
        includedAngle = 150

    elif quality == Quality.NORMAL:
        verticalRefinementLevel = 2
        insideRefinementLevel = 3
        verticalCentralRefinement = '((3 5) (10 3))'
        nCellsBetweenLevels = 3
        nSurfaceLayers = 3
        includedAngle = 170

    snappy_data['buildingModels'] = []
    analysis_bounds = None
    for b in building_models:
        if quality == Quality.QUICK:
            if b.type == MeshTypes.PRIMARY:
                feature_level = "4"
                refinementLevel = "(3 3)"
            else:
                feature_level = "3"
                refinementLevel = "3"
        elif quality == Quality.NORMAL:
            # feature_level = "((1 4) (3 3))"
            if b.type == MeshTypes.PRIMARY:
                feature_level = "5"
                refinementLevel = "(3 3)"
            else:
                feature_level = "3"
                refinementLevel = "(2 3)"
        if b.type == MeshTypes.PRIMARY:
            if analysis_bounds == None:
                analysis_bounds = b.rotated_bounds
            else:
                analysis_bounds[0][0] = min(analysis_bounds[0][0],b.rotated_bounds[0][0])
                analysis_bounds[0][1] = max(analysis_bounds[0][1],b.rotated_bounds[0][1])
                analysis_bounds[1][0] = min(analysis_bounds[1][0], b.rotated_bounds[1][0])
                analysis_bounds[1][1] = max(analysis_bounds[1][1], b.rotated_bounds[1][1])
                analysis_bounds[2][0] = min(analysis_bounds[2][0], b.rotated_bounds[2][0])
                analysis_bounds[2][1] = max(analysis_bounds[2][1], b.rotated_bounds[2][1])
        snappy_data['buildingModels'].append({
            'name': b.name.replace(' ', '_'),
            'filename': b.file_name,
            'file_basename': os.path.splitext(b.file_name)[0],
            'includedAngle': includedAngle,
            'feature_level': feature_level,
            'refinementLevel': refinementLevel
        })

    thirdheight = (analysis_bounds[2][1] - analysis_bounds[2][0]) / 3


    snappy_data['includedAngle'] = includedAngle
    snappy_data['verticalRefinementLevel'] = verticalRefinementLevel
    snappy_data['insideRefinementLevel'] = insideRefinementLevel
    snappy_data['verticalCentralRefinement'] = verticalCentralRefinement
    snappy_data['nCellsBetweenLevels'] = nCellsBetweenLevels
    snappy_data['nSurfaceLayers'] = nSurfaceLayers


    snappy_data['analysis_minx'] = analysis_bounds[0][0]-windtunnel_data['cell_size']
    snappy_data['analysis_maxx'] = analysis_bounds[0][1]+windtunnel_data['cell_size']
    snappy_data['analysis_miny'] = analysis_bounds[1][0] - windtunnel_data['cell_size']
    snappy_data['analysis_maxy'] = analysis_bounds[1][1] + windtunnel_data['cell_size']
    snappy_data['analysis_minz'] = analysis_bounds[2][0]
    snappy_data['analysis_maxz'] = analysis_bounds[2][1]
    snappy_data['thirdheight'] = thirdheight


    snappy_data['locationInMesh_x'] = windtunnel_data['background_minx'] + 1
    snappy_data['locationInMesh_y'] = windtunnel_data['background_miny'] + 1
    snappy_data['locationInMesh_z'] = windtunnel_data['background_maxz'] - 1

    return snappy_data