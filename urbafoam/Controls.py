from . import Quality

def setup_controls(quality):
    control_data = {}
    control_data['application'] = 'simpleFoam'
    control_data['startFrom'] = 'latestTime'

    if quality == Quality.QUICK:
        endTime = 800
        deltaT = 2
        writeInterval = 100
    elif quality == Quality.NORMAL:
        endTime = 1200
        deltaT = 1
        writeInterval = 400
    control_data['endTime'] = endTime
    control_data['deltaT'] = deltaT
    control_data['writeInterval'] = writeInterval
    control_data['purgeWrite'] = 1
    control_data['controlFunctions'] = []
    return control_data