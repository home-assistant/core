"""
Low-level utility functions for the PAJ GPS coordinator.

Responsibilities:
- Fetch elevation data from the Open-Meteo HTTP API.
- Produce immutable copies of Device objects with an alert flag toggled.

No HA imports — these functions are pure data / network primitives.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from pajgps_api.models.device import Device

from .const import ELEVATION_API_URL, ALERT_TYPE_TO_DEVICE_FIELD

_LOGGER = logging.getLogger(__name__)


async def fetch_elevation(lat: float, lng: float) -> float | None:
    """
    Fetch elevation (metres) from the Open-Meteo API for the given coordinates.

    Rounds lat/lng to ~100 m precision to improve remote cache hit rate.
    Returns None on any error so callers can handle the absence gracefully.
    """
    # ToDo: Fetching elevation have to be modified to either use data from PAJ GPS API when they start providing it or use open-meteo library when they merge pull request https://github.com/frenck/python-open-meteo/pull/1305
    rounded_lat = round(lat, 5)
    rounded_lng = round(lng, 5)
    params = {"latitude": rounded_lat, "longitude": rounded_lng}
    headers = {"accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(ELEVATION_API_URL, headers=headers, params=params) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Elevation API returned HTTP %s for (%.5f, %.5f)",
                        resp.status, rounded_lat, rounded_lng,
                    )
                    return None
                raw = await resp.json()
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Timeout fetching elevation for (%.5f, %.5f)", rounded_lat, rounded_lng
        )
        return None
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error(
            "Unexpected error fetching elevation for (%.5f, %.5f): %s",
            rounded_lat, rounded_lng, exc,
        )
        return None

    if raw and "elevation" in raw:
        return raw["elevation"][0]

    _LOGGER.warning(
        "Unexpected elevation response for (%.5f, %.5f): %s",
        rounded_lat, rounded_lng, raw,
    )
    return None


def apply_alert_flag(device: Device, alert_type: int, enabled: bool) -> Device:
    """
    Return a copy of device with the relevant alarm flag set to enabled/disabled.

    Device uses a plain custom BaseModel backed by __dict__, so we copy via
    __dict__ and construct a new instance, keeping the original immutable.
    """
    field = ALERT_TYPE_TO_DEVICE_FIELD.get(alert_type)
    if field is None:
        return device
    data = dict(device.__dict__)
    data[field] = 1 if enabled else 0
    return Device(**data)
