"""Conftest for Weather tests."""
from collections.abc import Generator

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant

from .common import (
    TEST_DOMAIN,
    MockWeatherTestEntity,
    mock_config_entry_setup,
    mock_setup,
)

from tests.common import mock_config_flow, mock_platform


@pytest.fixture
def mock_weather_entity() -> MockWeatherTestEntity:
    """Test Weather entity."""
    return MockWeatherTestEntity()


class WeatherFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(
    recorder_mock: Recorder, hass: HomeAssistant
) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, WeatherFlow):
        yield


@pytest.fixture(name="setup")
async def setup_fixture(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_weather_entity: MockWeatherTestEntity,
) -> None:
    """Set up the test environment."""
    if request.param == "mock_setup":
        await mock_setup(hass, mock_weather_entity)
    elif request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, mock_weather_entity)
    else:
        raise RuntimeError("Invalid setup fixture")
