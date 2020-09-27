import os

from . import Quality, MeshTypes
from .Config import get_or_update_config, get_value


def setup_snappy(config, windtunnel_data, building_models, quality):
    config_group = "urbafoam.snappy"
    snappy_data = {}
    if quality == Quality.QUICK:
        verticalRefinementLevel = get_or_update_config(config, config_group, "verticalDomainRefinement", 2)
        insideRefinementLevel = get_or_update_config(config, config_group, "CentralRefinement", 2)
        verticalCentralRefinement = get_or_update_config(config, config_group, "verticalCentralRefinement", [4, 2])
        verticalCentralRefinement = f'((3 {verticalCentralRefinement[0]}) (12 {verticalCentralRefinement[1]}))'
        nCellsBetweenLevels = get_or_update_config(config, config_group, "CellsBetweenLevels", 2)
        nSurfaceLayers = get_or_update_config(config, config_group, "SurfaceLayers", 2)
        includedAngle = get_or_update_config(config, config_group, "IncludeAngle", 150)

        primary_feature_level = get_or_update_config(config, config_group, "PrimaryFeatureLevel", 4)
        surrounding_feature_level = get_or_update_config(config, config_group, "SurroundingFeatureLevel", 3)
        primary_model_refinement_level = get_or_update_config(config, config_group, "PrimaryModelRefinementLevel",
                                                              '(2 4)')
        surrounding_model_refinement_level = get_or_update_config(config, config_group,
                                                                  "SurroundingModelRefinementLevel", '(2 2)')

    elif quality == Quality.NORMAL:
        verticalRefinementLevel = get_or_update_config(config, config_group, "verticalDomainRefinement", 2)
        insideRefinementLevel = get_or_update_config(config, config_group, "CentralRefinement", 3)
        verticalCentralRefinement = get_or_update_config(config, config_group, "verticalCentralRefinement", [5, 3])
        verticalCentralRefinement = f'((3 {verticalCentralRefinement[0]}) (12 {verticalCentralRefinement[1]}))'
        nCellsBetweenLevels = get_or_update_config(config, config_group, "CellsBetweenLevels", 3)
        nSurfaceLayers = get_or_update_config(config, config_group, "SurfaceLayers", 3)
        includedAngle = get_or_update_config(config, config_group, "IncludeAngle", 170)

        primary_feature_level = get_or_update_config(config, config_group, "PrimaryFeatureLevel", 5)
        surrounding_feature_level = get_or_update_config(config, config_group, "SurroundingFeatureLevel", 3)
        primary_model_refinement_level = get_or_update_config(config, config_group, "PrimaryModelRefinementLevel",
                                                              '(3 3)')
        surrounding_model_refinement_level = get_or_update_config(config, config_group,
                                                                  "SurroundingModelRefinementLevel", '(2 3)')

    snappy_data['buildingModels'] = []
    analysis_bounds = None
    for b in building_models:
        if b.type == MeshTypes.PRIMARY:
            feature_level = primary_feature_level
            refinementLevel = primary_model_refinement_level
            if analysis_bounds == None:
                analysis_bounds = b.rotated_bounds
            else:
                analysis_bounds[0][0] = min(analysis_bounds[0][0], b.rotated_bounds[0][0])
                analysis_bounds[0][1] = max(analysis_bounds[0][1], b.rotated_bounds[0][1])
                analysis_bounds[1][0] = min(analysis_bounds[1][0], b.rotated_bounds[1][0])
                analysis_bounds[1][1] = max(analysis_bounds[1][1], b.rotated_bounds[1][1])
                analysis_bounds[2][0] = min(analysis_bounds[2][0], b.rotated_bounds[2][0])
                analysis_bounds[2][1] = max(analysis_bounds[2][1], b.rotated_bounds[2][1])
        elif b.type == MeshTypes.SURROUNDING:
            feature_level = surrounding_feature_level
            refinementLevel = surrounding_model_refinement_level

        snappy_data['buildingModels'].append({
            'name': b.name.replace(' ', '_'),
            'filename': b.file_name,
            'file_basename': os.path.splitext(b.file_name)[0],
            'includedAngle': includedAngle,
            'featureLevel': feature_level,
            'refinementLevel': refinementLevel
        })

    thirdheight = (analysis_bounds[2][1] - analysis_bounds[2][0]) / 3

    snappy_data['includedAngle'] = includedAngle
    snappy_data['verticalRefinementLevel'] = verticalRefinementLevel
    snappy_data['insideRefinementLevel'] = insideRefinementLevel
    snappy_data['verticalCentralRefinement'] = verticalCentralRefinement
    snappy_data['nCellsBetweenLevels'] = nCellsBetweenLevels
    snappy_data['nSurfaceLayers'] = nSurfaceLayers

    analysis_area_buffer = get_value(config,"urbafoam.postprocess","sampleBuffer")
    analysis_area_buffer *= 1.5
    snappy_data['analysis_minx'] = analysis_bounds[0][0] - analysis_area_buffer
    snappy_data['analysis_maxx'] = analysis_bounds[0][1] + analysis_area_buffer
    snappy_data['analysis_miny'] = analysis_bounds[1][0] - analysis_area_buffer
    snappy_data['analysis_maxy'] = analysis_bounds[1][1] + analysis_area_buffer
    snappy_data['analysis_minz'] = analysis_bounds[2][0]
    snappy_data['analysis_maxz'] = analysis_bounds[2][1]
    snappy_data['thirdheight'] = thirdheight

    snappy_data['locationInMesh_x'] = windtunnel_data['background_minx'] + 1
    snappy_data['locationInMesh_y'] = windtunnel_data['background_miny'] + 1
    snappy_data['locationInMesh_z'] = windtunnel_data['background_maxz'] - 1

    return snappy_data
