def ensure_list(parameter):
    return parameter if isinstance(parameter, list) else [parameter]

def matcher(subject, pattern):
    return '*' in pattern or subject in pattern
