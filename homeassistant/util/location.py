"""Module with location helpers."""
import collections

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
