""" Helper methods for various modules. """

import datetime
import re

RE_SANITIZE_FILENAME = re.compile(r"(~|(\.\.)|/|\+)")
RE_SLUGIFY = re.compile(r'[^A-Za-z0-9_]+')

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"


def sanitize_filename(filename):
    """ Sanitizes a filename by removing .. / and \\. """
    return RE_SANITIZE_FILENAME.sub("", filename)


def slugify(text):
    """ Slugifies a given text. """
    text = text.strip().replace(" ", "_")

    return RE_SLUGIFY.sub("", text)


def datetime_to_str(dattim):
    """ Converts datetime to a string format.

    @rtype : str
    """
    return dattim.strftime(DATE_STR_FORMAT)


def str_to_datetime(dt_str):
    """ Converts a string to a datetime object.

    @rtype: datetime
    """
    try:
        return datetime.datetime.strptime(dt_str, DATE_STR_FORMAT)
    except ValueError:  # If dt_str did not match our format
        return None
