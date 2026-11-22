from pathlib import Path

from .Enums import MeshTypes


def setup_snappy(snappy_cfg, sample_buffer, windtunnel_data, building_models):
    snappy_data = {}
    verticalCentralRefinement = (f'((3 {snappy_cfg.verticalCentralRefinement[0]}) '
                                 f'(12 {snappy_cfg.verticalCentralRefinement[1]}))')
    includedAngle = snappy_cfg.IncludeAngle

    snappy_data['buildingModels'] = []
    analysis_bounds = None
    for b in building_models:
        if b is None:
            continue
        if b.type == MeshTypes.PRIMARY:
            feature_level = snappy_cfg.PrimaryFeatureLevel
            refinementLevel = snappy_cfg.PrimaryModelRefinementLevel
            if analysis_bounds is None:
                analysis_bounds = [list(axis) for axis in b.rotated_bounds]
            else:
                analysis_bounds[0][0] = min(analysis_bounds[0][0], b.rotated_bounds[0][0])
                analysis_bounds[0][1] = max(analysis_bounds[0][1], b.rotated_bounds[0][1])
                analysis_bounds[1][0] = min(analysis_bounds[1][0], b.rotated_bounds[1][0])
                analysis_bounds[1][1] = max(analysis_bounds[1][1], b.rotated_bounds[1][1])
                analysis_bounds[2][0] = min(analysis_bounds[2][0], b.rotated_bounds[2][0])
                analysis_bounds[2][1] = max(analysis_bounds[2][1], b.rotated_bounds[2][1])
        elif b.type == MeshTypes.SURROUNDING:
            feature_level = snappy_cfg.SurroundingFeatureLevel
            refinementLevel = snappy_cfg.SurroundingModelRefinementLevel

        snappy_data['buildingModels'].append({
            'name': b.name,
            'filename': b.file_name,
            'file_basename': Path(b.file_name).stem,
            'includedAngle': includedAngle,
            'featureLevel': feature_level,
            'refinementLevel': refinementLevel
        })

    # the models reach below the ground (DataConversion.sink_into_ground): measure from the ground
    ground = float(windtunnel_data.get('background_minz', 0.0))
    thirdheight = (analysis_bounds[2][1] - ground) / 3

    snappy_data['includedAngle'] = includedAngle
    snappy_data['verticalRefinementLevel'] = snappy_cfg.verticalDomainRefinement
    snappy_data['insideRefinementLevel'] = snappy_cfg.CentralRefinement
    snappy_data['verticalCentralRefinement'] = verticalCentralRefinement
    snappy_data['nCellsBetweenLevels'] = snappy_cfg.CellsBetweenLevels
    snappy_data['addSurfaceLayers'] = str(snappy_cfg.addLayers).lower()
    snappy_data['nSurfaceLayers'] = snappy_cfg.SurfaceLayers
    snappy_data['resolveFeatureAngle'] = snappy_cfg.resolveFeatureAngle
    snappy_data['maxGlobalCells'] = snappy_cfg.maxGlobalCells

    analysis_area_buffer = sample_buffer * 1.5
    snappy_data['analysis_minx'] = analysis_bounds[0][0] - analysis_area_buffer
    snappy_data['analysis_maxx'] = analysis_bounds[0][1] + analysis_area_buffer
    snappy_data['analysis_miny'] = analysis_bounds[1][0] - analysis_area_buffer
    snappy_data['analysis_maxy'] = analysis_bounds[1][1] + analysis_area_buffer
    snappy_data['analysis_minz'] = ground
    snappy_data['analysis_maxz'] = analysis_bounds[2][1]
    snappy_data['thirdheight'] = thirdheight

    snappy_data['locationInMesh_x'] = windtunnel_data['background_minx'] + 1
    snappy_data['locationInMesh_y'] = windtunnel_data['background_miny'] + 1
    snappy_data['locationInMesh_z'] = windtunnel_data['background_maxz'] - 1

    return snappy_data
