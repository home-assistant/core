"""Common fixtures for the jewish_calendar tests."""

from collections.abc import AsyncGenerator, Generator, Iterable
import datetime as dt
from typing import NamedTuple
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from hdate.translator import set_language
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


class _LocationData(NamedTuple):
    timezone: str
    diaspora: bool
    lat: float
    lng: float
    candle_lighting: int


LOCATIONS = {
    "Jerusalem": _LocationData("Asia/Jerusalem", False, 31.7683, 35.2137, 40),
    "New York": _LocationData("America/New_York", True, 40.7128, -74.006, 18),
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.jewish_calendar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def location_data(request: pytest.FixtureRequest) -> _LocationData | None:
    """Return data based on location name."""
    if not hasattr(request, "param"):
        return None

    return LOCATIONS[request.param]


@pytest.fixture
def tz_info(hass: HomeAssistant, location_data: _LocationData | None) -> dt.tzinfo:
    """Return time zone info."""
    if location_data is None:
        return dt_util.get_time_zone(hass.config.time_zone)
    return dt_util.get_time_zone(location_data.timezone)


@pytest.fixture(name="test_time")
def _test_time(
    request: pytest.FixtureRequest, tz_info: dt.tzinfo
) -> dt.datetime | None:
    """Return localized test time based."""
    if not hasattr(request, "param"):
        return None

    return request.param.replace(tzinfo=tz_info)


@pytest.fixture
def results(
    request: pytest.FixtureRequest, tz_info: dt.tzinfo, language: str
) -> Iterable:
    """Return localized results."""
    if not hasattr(request, "param"):
        return None

    # If results are generated, by using the HDate library, we need to set the language
    set_language(language)

    if isinstance(request.param, dict):
        result = {
            key: value.replace(tzinfo=tz_info)
            if isinstance(value, dt.datetime)
            else value
            for key, value in request.param.items()
        }
        if "attr" in result and isinstance(result["attr"], dict):
            result["attr"] = {
                key: value() if callable(value) else value
                for key, value in result["attr"].items()
            }
        return result
    return request.param


@pytest.fixture
def havdalah_offset() -> int | None:
    """Return None if default havdalah offset is not specified."""
    return None


@pytest.fixture
def language() -> str:
    """Return default language value, unless language is parametrized."""
    return "en"


@pytest.fixture(autouse=True)
async def setup_hass(hass: HomeAssistant, location_data: _LocationData | None) -> None:
    """Set up Home Assistant for testing the jewish_calendar integration."""

    if location_data:
        await hass.config.async_set_time_zone(location_data.timezone)
        hass.config.latitude = location_data.lat
        hass.config.longitude = location_data.lng


@pytest.fixture
def config_entry(
    location_data: _LocationData | None,
    language: str,
    havdalah_offset: int | None,
) -> MockConfigEntry:
    """Set up the jewish_calendar integration for testing."""
    param_data = {}
    param_options = {}

    if location_data:
        param_data = {
            CONF_DIASPORA: location_data.diaspora,
            CONF_TIME_ZONE: location_data.timezone,
        }
        param_options[CONF_CANDLE_LIGHT_MINUTES] = location_data.candle_lighting

    if havdalah_offset:
        param_options[CONF_HAVDALAH_OFFSET_MINUTES] = havdalah_offset

    return MockConfigEntry(
        title=DEFAULT_NAME,
        domain=DOMAIN,
        data={CONF_LANGUAGE: language, **param_data},
        options=param_options,
    )


@pytest.fixture
async def setup_at_time(
    test_time: dt.datetime, hass: HomeAssistant, config_entry: MockConfigEntry
) -> AsyncGenerator[None]:
    """Set up the jewish_calendar integration at a specific time."""
    with freeze_time(test_time):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield
