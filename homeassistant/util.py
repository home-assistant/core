def matcher(subject, pattern):
    """ Returns True if subject matches the pattern.
        Pattern is either a list of allowed subjects or a '*'. """
    return '*' in pattern or subject in pattern
