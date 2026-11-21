def case_dir_name(wind_direction):
    """Directory name of the case for a wind direction: '270' for 270 or 270.0, '22.5' for 22.5."""
    w = float(wind_direction)
    return str(int(w)) if w.is_integer() else str(w)
