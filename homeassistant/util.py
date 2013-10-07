""" Helper methods for various modules. """

import re

def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return re.sub(r"(~|(\.\.)|/|\+)", "", filename)
