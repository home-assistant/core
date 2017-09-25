"""
Module with location helpers.

detect_location_info and elevation are mocked by default during tests.
"""
import collections
import math
from typing import Any, Optional, Tuple, Dict

import requests

ELEVATION_URL = 'http://maps.googleapis.com/maps/api/elevation/json'
FREEGEO_API = 'https://freegeoip.io/json/'
IP_API = 'http://ip-api.com/json'

# Constants from https://github.com/maurycyp/vincenty
# Earth ellipsoid according to WGS 84
# Axis a of the ellipsoid (Radius of the earth in meters)
AXIS_A = 6378137
# Flattening f = (a-b) / a
FLATTENING = 1 / 298.257223563
# Axis b of the ellipsoid in meters.
AXIS_B = 6356752.314245

MILES_PER_KILOMETER = 0.621371
MAX_ITERATIONS = 200
CONVERGENCE_THRESHOLD = 1e-12

LocationInfo = collections.namedtuple(
    "LocationInfo",
    ['ip', 'country_code', 'country_name', 'region_code', 'region_name',
     'city', 'zip_code', 'time_zone', 'latitude', 'longitude',
     'use_metric'])


def detect_location_info():
    """Detect location information."""
    data = _get_freegeoip()

    if data is None:
        data = _get_ip_api()

    if data is None:
        return None

    data['use_metric'] = data['country_code'] not in (
        'US', 'MM', 'LR')

    return LocationInfo(**data)


def distance(lat1, lon1, lat2, lon2):
    """Calculate the distance in meters between two points.

    Async friendly.
    """
    return vincenty((lat1, lon1), (lat2, lon2)) * 1000


def elevation(latitude, longitude):
    """Return elevation for given latitude and longitude."""
    try:
        req = requests.get(
            ELEVATION_URL,
            params={
                'locations': '{},{}'.format(latitude, longitude),
                'sensor': 'false',
            },
            timeout=10)
    except requests.RequestException:
        return 0

    if req.status_code != 200:
        return 0

    try:
        return int(float(req.json()['results'][0]['elevation']))
    except (ValueError, KeyError, IndexError):
        return 0


# Author: https://github.com/maurycyp
# Source: https://github.com/maurycyp/vincenty
# License: https://github.com/maurycyp/vincenty/blob/master/LICENSE
# pylint: disable=invalid-name, unused-variable, invalid-sequence-index
def vincenty(point1: Tuple[float, float], point2: Tuple[float, float],
             miles: bool=False) -> Optional[float]:
    """
    Vincenty formula (inverse method) to calculate the distance.

    Result in kilometers or miles between two points on the surface of a
    spheroid.

    Async friendly.
    """
    # short-circuit coincident points
    if point1[0] == point2[0] and point1[1] == point2[1]:
        return 0.0

    U1 = math.atan((1 - FLATTENING) * math.tan(math.radians(point1[0])))
    U2 = math.atan((1 - FLATTENING) * math.tan(math.radians(point2[0])))
    L = math.radians(point2[1] - point1[1])
    Lambda = L

    sinU1 = math.sin(U1)
    cosU1 = math.cos(U1)
    sinU2 = math.sin(U2)
    cosU2 = math.cos(U2)

    for iteration in range(MAX_ITERATIONS):
        sinLambda = math.sin(Lambda)
        cosLambda = math.cos(Lambda)
        sinSigma = math.sqrt((cosU2 * sinLambda) ** 2 +
                             (cosU1 * sinU2 - sinU1 * cosU2 * cosLambda) ** 2)
        if sinSigma == 0:
            return 0.0  # coincident points
        cosSigma = sinU1 * sinU2 + cosU1 * cosU2 * cosLambda
        sigma = math.atan2(sinSigma, cosSigma)
        sinAlpha = cosU1 * cosU2 * sinLambda / sinSigma
        cosSqAlpha = 1 - sinAlpha ** 2
        try:
            cos2SigmaM = cosSigma - 2 * sinU1 * sinU2 / cosSqAlpha
        except ZeroDivisionError:
            cos2SigmaM = 0
        C = FLATTENING / 16 * cosSqAlpha * (4 + FLATTENING * (4 - 3 *
                                                              cosSqAlpha))
        LambdaPrev = Lambda
        Lambda = L + (1 - C) * FLATTENING * sinAlpha * (sigma + C * sinSigma *
                                                        (cos2SigmaM + C *
                                                         cosSigma *
                                                         (-1 + 2 *
                                                          cos2SigmaM ** 2)))
        if abs(Lambda - LambdaPrev) < CONVERGENCE_THRESHOLD:
            break  # successful convergence
    else:
        return None  # failure to converge

    uSq = cosSqAlpha * (AXIS_A ** 2 - AXIS_B ** 2) / (AXIS_B ** 2)
    A = 1 + uSq / 16384 * (4096 + uSq * (-768 + uSq * (320 - 175 * uSq)))
    B = uSq / 1024 * (256 + uSq * (-128 + uSq * (74 - 47 * uSq)))
    deltaSigma = B * sinSigma * (cos2SigmaM +
                                 B / 4 * (cosSigma * (-1 + 2 *
                                                      cos2SigmaM ** 2) -
                                          B / 6 * cos2SigmaM *
                                          (-3 + 4 * sinSigma ** 2) *
                                          (-3 + 4 * cos2SigmaM ** 2)))
    s = AXIS_B * A * (sigma - deltaSigma)

    s /= 1000  # Conversion of meters to kilometers
    if miles:
        s *= MILES_PER_KILOMETER  # kilometers to miles

    return round(s, 6)


def _get_freegeoip() -> Optional[Dict[str, Any]]:
    """Query freegeoip.io for location data."""
    try:
        raw_info = requests.get(FREEGEO_API, timeout=5).json()
    except (requests.RequestException, ValueError):
        return None

    return {
        'ip': raw_info.get('ip'),
        'country_code': raw_info.get('country_code'),
        'country_name': raw_info.get('country_name'),
        'region_code': raw_info.get('region_code'),
        'region_name': raw_info.get('region_name'),
        'city': raw_info.get('city'),
        'zip_code': raw_info.get('zip_code'),
        'time_zone': raw_info.get('time_zone'),
        'latitude': raw_info.get('latitude'),
        'longitude': raw_info.get('longitude'),
    }


def _get_ip_api() -> Optional[Dict[str, Any]]:
    """Query ip-api.com for location data."""
    try:
        raw_info = requests.get(IP_API, timeout=5).json()
    except (requests.RequestException, ValueError):
        return None

    return {
        'ip': raw_info.get('query'),
        'country_code': raw_info.get('countryCode'),
        'country_name': raw_info.get('country'),
        'region_code': raw_info.get('region'),
        'region_name': raw_info.get('regionName'),
        'city': raw_info.get('city'),
        'zip_code': raw_info.get('zip'),
        'time_zone': raw_info.get('timezone'),
        'latitude': raw_info.get('lat'),
        'longitude': raw_info.get('lon'),
    }
