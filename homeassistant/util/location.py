"""Module with location helpers.

detect_location_info and elevation are mocked by default during tests.
"""
from __future__ import annotations

from functools import lru_cache
import math
from typing import Any, NamedTuple

import aiohttp

from homeassistant.const import __version__ as HA_VERSION

WHOAMI_URL = "https://services.home-assistant.io/whoami/v1"
WHOAMI_URL_DEV = "https://services-dev.home-assistant.workers.dev/whoami/v1"

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


class LocationInfo(NamedTuple):
    """Tuple with location information."""

    ip: str
    country_code: str
    currency: str
    region_code: str
    region_name: str
    city: str
    zip_code: str
    time_zone: str
    latitude: float
    longitude: float
    use_metric: bool


async def async_detect_location_info(
    session: aiohttp.ClientSession,
) -> LocationInfo | None:
    """Detect location information."""
    if (data := await _get_whoami(session)) is None:
        return None

    data["use_metric"] = data["country_code"] not in ("US", "MM", "LR")

    return LocationInfo(**data)


@lru_cache
def distance(
    lat1: float | None, lon1: float | None, lat2: float, lon2: float
) -> float | None:
    """Calculate the distance in meters between two points.

    Async friendly.
    """
    if lat1 is None or lon1 is None:
        return None
    result = vincenty((lat1, lon1), (lat2, lon2))
    if result is None:
        return None
    return result * 1000


# Author: https://github.com/maurycyp
# Source: https://github.com/maurycyp/vincenty
# License: https://github.com/maurycyp/vincenty/blob/master/LICENSE
def vincenty(
    point1: tuple[float, float], point2: tuple[float, float], miles: bool = False
) -> float | None:
    """Vincenty formula (inverse method) to calculate the distance.

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

    for _ in range(MAX_ITERATIONS):
        sinLambda = math.sin(Lambda)
        cosLambda = math.cos(Lambda)
        sinSigma = math.sqrt(
            (cosU2 * sinLambda) ** 2 + (cosU1 * sinU2 - sinU1 * cosU2 * cosLambda) ** 2
        )
        if sinSigma == 0.0:
            return 0.0  # coincident points
        cosSigma = sinU1 * sinU2 + cosU1 * cosU2 * cosLambda
        sigma = math.atan2(sinSigma, cosSigma)
        sinAlpha = cosU1 * cosU2 * sinLambda / sinSigma
        cosSqAlpha = 1 - sinAlpha**2
        try:
            cos2SigmaM = cosSigma - 2 * sinU1 * sinU2 / cosSqAlpha
        except ZeroDivisionError:
            cos2SigmaM = 0
        C = FLATTENING / 16 * cosSqAlpha * (4 + FLATTENING * (4 - 3 * cosSqAlpha))
        LambdaPrev = Lambda
        Lambda = L + (1 - C) * FLATTENING * sinAlpha * (
            sigma
            + C * sinSigma * (cos2SigmaM + C * cosSigma * (-1 + 2 * cos2SigmaM**2))
        )
        if abs(Lambda - LambdaPrev) < CONVERGENCE_THRESHOLD:
            break  # successful convergence
    else:
        return None  # failure to converge

    uSq = cosSqAlpha * (AXIS_A**2 - AXIS_B**2) / (AXIS_B**2)
    A = 1 + uSq / 16384 * (4096 + uSq * (-768 + uSq * (320 - 175 * uSq)))
    B = uSq / 1024 * (256 + uSq * (-128 + uSq * (74 - 47 * uSq)))
    # fmt: off
    deltaSigma = (
        B
        * sinSigma
        * (
            cos2SigmaM
            + B
            / 4
            * (
                cosSigma * (-1 + 2 * cos2SigmaM**2)
                - B
                / 6
                * cos2SigmaM
                * (-3 + 4 * sinSigma ** 2)
                * (-3 + 4 * cos2SigmaM ** 2)
            )
        )
    )
    # fmt: on
    s = AXIS_B * A * (sigma - deltaSigma)

    s /= 1000  # Conversion of meters to kilometers
    if miles:
        s *= MILES_PER_KILOMETER  # kilometers to miles

    return round(s, 6)


async def _get_whoami(session: aiohttp.ClientSession) -> dict[str, Any] | None:
    """Query whoami.home-assistant.io for location data."""
    try:
        resp = await session.get(
            WHOAMI_URL_DEV if HA_VERSION.endswith("0.dev0") else WHOAMI_URL, timeout=30
        )
    except (aiohttp.ClientError, TimeoutError):
        return None

    try:
        raw_info = await resp.json()
    except (aiohttp.ClientError, ValueError):
        return None

    return {
        "ip": raw_info.get("ip"),
        "country_code": raw_info.get("country"),
        "currency": raw_info.get("currency"),
        "region_code": raw_info.get("region_code"),
        "region_name": raw_info.get("region"),
        "city": raw_info.get("city"),
        "zip_code": raw_info.get("postal_code"),
        "time_zone": raw_info.get("timezone"),
        "latitude": float(raw_info.get("latitude")),
        "longitude": float(raw_info.get("longitude")),
    }
