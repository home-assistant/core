""" Helper methods for various modules. """

from datetime import datetime
import re

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"

def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return re.sub(r"(~|(\.\.)|/|\+)", "", filename)

def datetime_to_str(dattim):
    """ Converts datetime to a string format. """
    return dattim.strftime(DATE_STR_FORMAT)

def str_to_datetime(dt_str):
    """ Converts a string to a datetime object. """
    return datetime.strptime(dt_str, DATE_STR_FORMAT)
