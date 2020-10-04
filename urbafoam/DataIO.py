import fiona
import numpy as np
def writeWindPoints(basepoints,data,wind_dirs,out_file,format = 'csv'):
    format = format.replace('.','')
    format = format.lower()
    known_formats = ('csv','json','geojson','shp','shape')
    if format not in known_formats:
        raise ValueError(f'output type {format} not recognized. Must be one of {known_formats}')

    if format == 'csv':
        csv_dst = open(out_file,'w')
        header = "X,Y,Z"
        for w in wind_dirs:
            header += f",wind_dir{w}"
        header += '\n'
        csv_dst.write(header)
    else:
        schema = {'geometry': 'Point',
                'properties': {}}
        properties = []
        for w in wind_dirs:
            prop = f"w_dir{w}"
            properties.append(prop)
            schema['properties'][prop] = 'float'
        fiona_dst = fiona.open(out_file,'w',driver='ESRI Shapefile',schema=schema)
    for pt, d in zip(basepoints,zip(*data)):
        if format == 'csv':
            pt_string = ','.join(map(str,pt))
            data_string = ','.join(map(str,d))
            csv_dst.write(f'{pt_string},{data_string}\n')
        else:
            geom = {
                'type': 'Point',
                'coordinates': tuple(pt)
            }
            prop = {p:v for p,v in zip(properties,d)}
            fiona_dst.write({'geometry':geom,'properties':prop})


    if format == 'csv':
        csv_dst.close()
    else:
        fiona_dst.close()

def writeWindVectors(data,out_file,format = 'csv'):
    format = format.replace('.', '')
    format = format.lower()
    known_formats = ('csv', 'json', 'geojson', 'shp', 'shape')
    if format not in known_formats:
        raise ValueError(f'output type {format} not recognized. Must be one of {known_formats}')

    if format == 'csv':
        header = "start_X,start_Y,start_Z,end_X,end_Y,end_Z,mag"
        np.savetxt(out_file,data,delimiter=',',header=header,comments='')
    else:
        schema = {'geometry': 'LineString',
                  'properties': {'mag':'float'}}
        with fiona.open(out_file,'w',driver='ESRI Shapefile',schema=schema) as dst:
            for d in data:
                geom = {"type": "LineString", "coordinates": [ d[:3],d[3:6]]}
                prop = {'mag':d[6]}
                dst.write({'geometry':geom,'properties':prop})



