"""The tests for Radarr sensor platform."""

import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
@pytest.mark.parametrize(
    ("windows", "single", "root_folder"),
    [
        (
            False,
            False,
            "downloads",
        ),
        (
            False,
            True,
            "downloads",
        ),
        (
            True,
            False,
            "tv",
        ),
        (
            True,
            True,
            "tv",
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry_enabled_by_default: None,
    windows: bool,
    single: bool,
    root_folder: str,
) -> None:
    """Test for successfully setting up the Radarr platform."""
    await setup_integration(hass, aioclient_mock, windows=windows, single_return=single)

    state = hass.states.get(f"sensor.mock_title_disk_space_{root_folder}")
    assert state.state == "263.10"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    state = hass.states.get("sensor.mock_title_movies")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Movies"
    state = hass.states.get("sensor.mock_title_start_time")
    assert state.state == "2020-09-01T23:50:20+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.mock_title_queue")
    assert state.state == "2"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Movies"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL


@pytest.mark.freeze_time("2021-12-03 00:00:00+00:00")
async def test_windows(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test for successfully setting up the Radarr platform on Windows."""
    await setup_integration(hass, aioclient_mock, windows=True)

    state = hass.states.get("sensor.mock_title_disk_space_tv")
    assert state.state == "263.10"
