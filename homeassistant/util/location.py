"""
Module with location helpers.

detect_location_info and elevation are mocked by default during tests.
"""
import collections

import requests

from vincenty import vincenty

ELEVATION_URL = 'http://maps.googleapis.com/maps/api/elevation/json'

LocationInfo = collections.namedtuple(
    "LocationInfo",
    ['ip', 'country_code', 'country_name', 'region_code', 'region_name',
     'city', 'zip_code', 'time_zone', 'latitude', 'longitude',
     'use_fahrenheit'])


def detect_location_info():
    """Detect location information."""
    try:
        raw_info = requests.get(
            'https://freegeoip.net/json/', timeout=5).json()
    except (requests.RequestException, ValueError):
        return None

    data = {key: raw_info.get(key) for key in LocationInfo._fields}

    # From Wikipedia: Fahrenheit is used in the Bahamas, Belize,
    # the Cayman Islands, Palau, and the United States and associated
    # territories of American Samoa and the U.S. Virgin Islands
    data['use_fahrenheit'] = data['country_code'] in (
        'BS', 'BZ', 'KY', 'PW', 'US', 'AS', 'VI')

    return LocationInfo(**data)


def distance(lat1, lon1, lat2, lon2):
    """Calculate the distance in meters between two points."""
    return vincenty((lat1, lon1), (lat2, lon2)) * 1000


def elevation(latitude, longitude):
    """Return elevation for given latitude and longitude."""
    req = requests.get(ELEVATION_URL, params={
        'locations': '{},{}'.format(latitude, longitude),
        'sensor': 'false',
    })

    if req.status_code != 200:
        return 0

    try:
        return int(float(req.json()['results'][0]['elevation']))
    except (ValueError, KeyError):
        return 0
