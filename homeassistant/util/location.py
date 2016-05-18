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

DATA_SOURCE = ['https://freegeoip.io/json/', 'http://ip-api.com/json']


def detect_location_info():
    """Detect location information."""
    success = None

    for source in DATA_SOURCE:
        try:
            raw_info = requests.get(source, timeout=5).json()
            success = source
            break
        except (requests.RequestException, ValueError):
            success = False

    if success is False:
        return None
    else:
        data = {key: raw_info.get(key) for key in LocationInfo._fields}
        if success is DATA_SOURCE[1]:
            data['ip'] = raw_info.get('query')
            data['country_code'] = raw_info.get('countryCode')
            data['country_name'] = raw_info.get('country')
            data['region_code'] = raw_info.get('region')
            data['region_name'] = raw_info.get('regionName')
            data['zip_code'] = raw_info.get('zip')
            data['time_zone'] = raw_info.get('timezone')
            data['latitude'] = raw_info.get('lat')
            data['longitude'] = raw_info.get('lon')

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
    req = requests.get(ELEVATION_URL,
                       params={'locations': '{},{}'.format(latitude,
                                                           longitude),
                               'sensor': 'false'},
                       timeout=10)

    if req.status_code != 200:
        return 0

    try:
        return int(float(req.json()['results'][0]['elevation']))
    except (ValueError, KeyError):
        return 0
