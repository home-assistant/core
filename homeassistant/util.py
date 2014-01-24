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


def split_entity_id(entity_id):
    """ Splits a state entity_id into domain, object_id. """
    return entity_id.split(".", 1)


def filter_entity_ids(entity_ids, domain_filter=None, strip_domain=False):
    """ Filter a list of entities based on domain. Setting strip_domain
        will only return the object_ids. """
    return [
        split_entity_id(entity_id)[1] if strip_domain else entity_id
        for entity_id in entity_ids if
        not domain_filter or entity_id.startswith(domain_filter)
        ]
