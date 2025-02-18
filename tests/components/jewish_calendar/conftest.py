"""Common fixtures for the jewish_calendar tests."""

from collections.abc import Generator
import datetime as dt
from typing import NamedTuple
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_LOCATION, CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


class _LatLng(NamedTuple):
    lat: float
    lng: float


LOCATIONS = {
    "Jerusalem": ("Asia/Jerusalem", _LatLng(31.7683, 35.2137), 40),
    "NYC": ("America/New_York", _LatLng(40.7128, -74.006), 18),
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.jewish_calendar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def jcal_params(request: pytest.FixtureRequest) -> dict | None:
    """Return test parameters."""
    if not hasattr(request, "param"):
        return None

    if len(request.param) == 3:
        location_name, dtime, results = request.param
        havdalah_offset = 0

    if len(request.param) == 4:
        location_name, dtime, results, havdalah_offset = request.param

    time_zone, latlng, candle_light = LOCATIONS[location_name]
    tz_info = dt_util.get_time_zone(time_zone)
    dtime = dtime.replace(tzinfo=tz_info)
    if isinstance(results, dict):
        results = {
            key: value.replace(tzinfo=tz_info)
            if isinstance(value, dt.datetime)
            else value
            for key, value in results.items()
        }

    return {
        "dtime": dtime,
        "results": results,
        CONF_TIME_ZONE: time_zone,
        CONF_DIASPORA: location_name not in ("Jerusalem",),
        CONF_LOCATION: latlng,
        CONF_CANDLE_LIGHT_MINUTES: candle_light,
        CONF_HAVDALAH_OFFSET_MINUTES: havdalah_offset,
    }


@pytest.fixture
def language(request: pytest.FixtureRequest) -> str:
    """Return language."""
    return getattr(request, "param", "english")


@pytest.fixture
async def setup_hass(hass: HomeAssistant, jcal_params: dict | None) -> None:
    """Set up Home Assistant for testing the jewish_calendar integration."""

    if jcal_params:
        await hass.config.async_set_time_zone(jcal_params[CONF_TIME_ZONE])
        hass.config.latitude = jcal_params[CONF_LOCATION].lat
        hass.config.longitude = jcal_params[CONF_LOCATION].lng


@pytest.fixture
def config_entry(jcal_params: dict | None, language: str) -> MockConfigEntry:
    """Set up the jewish_calendar integration for testing."""
    param_data = {}
    param_options = {}

    if jcal_params:
        param_data = {
            CONF_DIASPORA: jcal_params[CONF_DIASPORA],
            CONF_TIME_ZONE: jcal_params[CONF_TIME_ZONE],
        }
        param_options = {
            CONF_CANDLE_LIGHT_MINUTES: jcal_params[CONF_CANDLE_LIGHT_MINUTES],
            CONF_HAVDALAH_OFFSET_MINUTES: jcal_params[CONF_HAVDALAH_OFFSET_MINUTES],
        }

    return MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
        data={CONF_LANGUAGE: language, **param_data},
        options=param_options,
    )
