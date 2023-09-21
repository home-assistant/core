"""The tests for Radarr sensor platform."""
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


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
