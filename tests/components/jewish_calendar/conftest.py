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
from homeassistant.const import (
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_TIME_ZONE,
)
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
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
    )


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

    location_name, dtime, results, havdalah_offset = request.param
    time_zone, latlng, candle_light = LOCATIONS[location_name]

    tz_info = dt_util.get_time_zone(time_zone)
    if isinstance(results, dict):
        results = {
            key: value.replace(tzinfo=time_zone)
            if isinstance(value, dt.datetime)
            else value
            for key, value in results.items()
        }

    return {
        "dtime": dtime,
        "results": results,
        CONF_TIME_ZONE: tz_info,
        CONF_DIASPORA: location_name in ("jerusalem",),
        CONF_LOCATION: latlng,
        CONF_CANDLE_LIGHT_MINUTES: candle_light,
        CONF_HAVDALAH_OFFSET_MINUTES: havdalah_offset,
    }


@pytest.fixture
def language(request: pytest.FixtureRequest) -> str:
    """Return language."""
    return getattr(request, "param", "english")


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, jcal_params: dict | None, language: str
) -> MockConfigEntry:
    """Set up the jewish_calendar integration for testing."""

    entry = MockConfigEntry(
        title=DEFAULT_NAME, domain=DOMAIN, data={CONF_LANGUAGE: language}
    )

    if jcal_params:
        entry.data |= {
            CONF_DIASPORA: jcal_params["diaspora"],
            CONF_TIME_ZONE: jcal_params["time_zone"],
            CONF_LOCATION: {
                CONF_LATITUDE: jcal_params["latlng"].lat,
                CONF_LONGITUDE: jcal_params["latlng"].lng,
            },
        }
        entry.options = {
            CONF_CANDLE_LIGHT_MINUTES: jcal_params["candle_light"],
            CONF_HAVDALAH_OFFSET_MINUTES: jcal_params["havdalah_offset"],
        }

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
