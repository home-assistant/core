"""Helpers for moon phases."""

import asyncio
import logging
import os
from typing import NamedTuple

import aiohttp
from skyfield import almanac
from skyfield.api import Loader
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Timescale

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.singleton import singleton
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STATE_FIRST_QUARTER = "first_quarter"
STATE_FULL_MOON = "full_moon"
STATE_LAST_QUARTER = "last_quarter"
STATE_NEW_MOON = "new_moon"
STATE_WANING_CRESCENT = "waning_crescent"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_WAXING_CRESCENT = "waxing_crescent"
STATE_WAXING_GIBBOUS = "waxing_gibbous"

# The eight moon phases in chronological order (new moon to waning crescent).
MOON_PHASES: tuple[str, ...] = (
    STATE_NEW_MOON,
    STATE_WAXING_CRESCENT,
    STATE_FIRST_QUARTER,
    STATE_WAXING_GIBBOUS,
    STATE_FULL_MOON,
    STATE_WANING_GIBBOUS,
    STATE_LAST_QUARTER,
    STATE_WANING_CRESCENT,
)

# Scale Skyfield's phase angle to the 28-day scale used by the phase thresholds.
_LUNAR_CYCLE_DAYS = 28
_FULL_MOON_PHASE_VALUE = 14


class MoonData(NamedTuple):
    """The ephemeris and timescale used for moon calculations."""

    ephemeris: SpiceKernel
    timescale: Timescale


DATA_MOON: HassKey[MoonData] = HassKey(DOMAIN)

EPHEMERIS_FILE = "de421.bsp"
EPHEMERIS_URL = f"https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/{EPHEMERIS_FILE}"
EPHEMERIS_DOWNLOAD_TIMEOUT = 300


def _load_moon_data(directory: str) -> MoonData:
    """Load the planetary ephemeris and built-in timescale from disk."""
    loader = Loader(directory)
    moon_data = MoonData(loader(EPHEMERIS_FILE), loader.timescale(builtin=True))
    # The first Skyfield calculation is slow; pay that cost here, not in the event loop.
    _phase_value(moon_data)
    return moon_data


def _write_ephemeris(path: str, content: bytes) -> None:
    """Write the ephemeris atomically so an interrupted download is never loaded."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "wb") as file:
        file.write(content)
    os.replace(temp_path, path)


async def _async_download_ephemeris(hass: HomeAssistant, path: str) -> None:
    """Download the planetary ephemeris into the cache directory."""
    session = async_get_clientsession(hass)
    try:
        async with (
            asyncio.timeout(EPHEMERIS_DOWNLOAD_TIMEOUT),
            session.get(EPHEMERIS_URL) as response,
        ):
            response.raise_for_status()
            content = await response.read()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise OSError(f"Unable to download {EPHEMERIS_URL}") from err
    await hass.async_add_executor_job(_write_ephemeris, path, content)


async def _async_download_and_load(
    hass: HomeAssistant, directory: str, path: str
) -> MoonData:
    """Download the ephemeris and load it, raising OSError if it is unreadable."""
    await _async_download_ephemeris(hass, path)
    try:
        return await hass.async_add_executor_job(_load_moon_data, directory)
    except Exception as err:
        raise OSError(f"Unable to load {path}") from err


@singleton(DATA_MOON, async_=True)
async def async_get_moon_data(hass: HomeAssistant) -> MoonData:
    """Return the shared moon data, downloading and loading it on first use.

    Raises OSError if the ephemeris cannot be downloaded or read.
    """
    directory = hass.config.cache_path("skyfield")
    path = os.path.join(directory, EPHEMERIS_FILE)
    if await hass.async_add_executor_job(os.path.isfile, path):
        try:
            moon_data = await hass.async_add_executor_job(_load_moon_data, directory)
        except Exception:  # noqa: BLE001 - a corrupt file can raise any error type
            _LOGGER.warning("Ephemeris %s is unreadable, downloading it again", path)
            await hass.async_add_executor_job(os.remove, path)
            moon_data = await _async_download_and_load(hass, directory, path)
    else:
        moon_data = await _async_download_and_load(hass, directory, path)

    @callback
    def _close_ephemeris(_event: Event) -> None:
        moon_data.ephemeris.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close_ephemeris)
    return moon_data


@callback
def _phase_value(moon_data: MoonData) -> float:
    """Return the current moon phase on a 28-day scale."""
    now = dt_util.utcnow()
    time = moon_data.timescale.from_datetime(now)
    phase_angle = almanac.moon_phase(moon_data.ephemeris, time).degrees
    return float(phase_angle * (_LUNAR_CYCLE_DAYS / 360))


@callback
def moon_phase(moon_data: MoonData) -> str:
    """Return the current moon phase."""
    value = _phase_value(moon_data)
    if value < 0.5 or value > 27.5:
        return STATE_NEW_MOON
    if value < 6.5:
        return STATE_WAXING_CRESCENT
    if value < 7.5:
        return STATE_FIRST_QUARTER
    if value < 13.5:
        return STATE_WAXING_GIBBOUS
    if value < 14.5:
        return STATE_FULL_MOON
    if value < 20.5:
        return STATE_WANING_GIBBOUS
    if value < 21.5:
        return STATE_LAST_QUARTER
    return STATE_WANING_CRESCENT


@callback
def is_waxing(moon_data: MoonData) -> bool:
    """Return whether the moon is currently waxing (illumination increasing)."""
    value = _phase_value(moon_data)
    return value < _FULL_MOON_PHASE_VALUE
