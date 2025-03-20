"""Common fixtures for the jewish_calendar tests."""

from collections.abc import Generator
from dataclasses import dataclass
import datetime as dt
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


class _LatLng(NamedTuple):
    lat: float
    lng: float


@dataclass
class JewishCalendarTestParameters:
    """Test parameters for a Jewish calendar test."""

    test_time: dt.datetime
    results: dict[str, Any] | dt.datetime
    time_zone: str
    diaspora: bool
    location: _LatLng
    candle_light_minutes: int
    havdalah_offset_minutes: int


LOCATIONS = {
    "Jerusalem": ("Asia/Jerusalem", _LatLng(31.7683, 35.2137), 40),
    "New York": ("America/New_York", _LatLng(40.7128, -74.006), 18),
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.jewish_calendar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def jcal_params(request: pytest.FixtureRequest) -> JewishCalendarTestParameters | None:
    """Return test parameters."""
    if not hasattr(request, "param"):
        return None

    if len(request.param) == 3:
        location_name, test_time, results = request.param
        havdalah_offset = 0

    if len(request.param) == 4:
        location_name, test_time, results, havdalah_offset = request.param

    time_zone, latlng, candle_light = LOCATIONS[location_name]
    tz_info = dt_util.get_time_zone(time_zone)
    test_time = test_time.replace(tzinfo=tz_info)
    if isinstance(results, dict):
        results = {
            key: value.replace(tzinfo=tz_info)
            if isinstance(value, dt.datetime)
            else value
            for key, value in results.items()
        }

    return JewishCalendarTestParameters(
        test_time,
        results,
        time_zone,
        location_name not in ("Jerusalem",),
        latlng,
        candle_light,
        havdalah_offset,
    )


@pytest.fixture
def language(request: pytest.FixtureRequest) -> str:
    """Return default language value, unless language is parametrized."""
    return getattr(request, "param", "english")


@pytest.fixture(autouse=True)
async def setup_hass(
    hass: HomeAssistant, jcal_params: JewishCalendarTestParameters | None
) -> None:
    """Set up Home Assistant for testing the jewish_calendar integration."""

    if jcal_params:
        await hass.config.async_set_time_zone(jcal_params.time_zone)
        hass.config.latitude = jcal_params.location.lat
        hass.config.longitude = jcal_params.location.lng


@pytest.fixture
def config_entry(
    jcal_params: JewishCalendarTestParameters | None, language: str
) -> MockConfigEntry:
    """Set up the jewish_calendar integration for testing."""
    param_data = {}
    param_options = {}

    if jcal_params:
        param_data = {
            CONF_DIASPORA: jcal_params.diaspora,
            CONF_TIME_ZONE: jcal_params.time_zone,
        }
        param_options = {
            CONF_CANDLE_LIGHT_MINUTES: jcal_params.candle_light_minutes,
            CONF_HAVDALAH_OFFSET_MINUTES: jcal_params.havdalah_offset_minutes,
        }

    return MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
        data={CONF_LANGUAGE: language, **param_data},
        options=param_options,
    )
