"""Module with location helpers."""
import collections
from math import radians, cos, sin, asin, sqrt

import requests


LocationInfo = collections.namedtuple(
    "LocationInfo",
    ['ip', 'country_code', 'country_name', 'region_code', 'region_name',
     'city', 'zip_code', 'time_zone', 'latitude', 'longitude',
     'use_fahrenheit'])


def detect_location_info():
    """ Detect location information. """
    try:
        raw_info = requests.get(
            'https://freegeoip.net/json/', timeout=5).json()
    except requests.RequestException:
        return

    data = {key: raw_info.get(key) for key in LocationInfo._fields}

    # From Wikipedia: Fahrenheit is used in the Bahamas, Belize,
    # the Cayman Islands, Palau, and the United States and associated
    # territories of American Samoa and the U.S. Virgin Islands
    data['use_fahrenheit'] = data['country_code'] in (
        'BS', 'BZ', 'KY', 'PW', 'US', 'AS', 'VI')

    return LocationInfo(**data)


# From: http://stackoverflow.com/a/4913653/646416
def distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in meters between two points specified
    in decimal degrees on the earth using the Haversine algorithm.
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    # Radius of earth in meters.
    radius = 6371000
    return c * radius
