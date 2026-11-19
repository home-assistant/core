"""The tests for Lidarr sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from aiopyarr import LidarrRootFolder
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import ComponentSetup


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    connection,
) -> None:
    """Test for successfully setting up the Lidarr platform."""
    await setup_integration()

    state = hass.states.get("sensor.mock_title_disk_space")
    assert state.state == "0.93"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    state = hass.states.get("sensor.mock_title_queue")
    assert state.state == "2"
    assert state.attributes.get("string") == "stopped"
    assert state.attributes.get("string2") == "downloading"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "albums"
    assert state.attributes.get(CONF_STATE_CLASS) == SensorStateClass.TOTAL
    state = hass.states.get("sensor.mock_title_wanted")
    assert state.state == "1"
    assert state.attributes.get("test") == "test"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "albums"
    assert state.attributes.get(CONF_STATE_CLASS) == SensorStateClass.TOTAL
    state = hass.states.get("sensor.mock_title_albums")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "albums"
    assert state.attributes.get(CONF_STATE_CLASS) == SensorStateClass.TOTAL


@pytest.mark.parametrize(
    "root_folder",
    [
        pytest.param({"path": "/music/", "accessible": True}, id="free_space_missing"),
        pytest.param({"path": "/music/", "accessible": False}, id="inaccessible"),
    ],
)
@pytest.mark.usefixtures("connection")
async def test_disk_space_unknown_when_free_space_missing(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    root_folder: dict[str, str | bool],
) -> None:
    """Test disk space is unknown while Lidarr can't report a folder's free space."""
    await setup_integration()
    entity = "sensor.mock_title_disk_space"
    assert hass.states.get(entity).state == "0.93"

    with patch(
        "homeassistant.components.lidarr.coordinator.LidarrClient.async_get_root_folders",
        return_value=[LidarrRootFolder(root_folder)],
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
        await hass.async_block_till_done()

    assert hass.states.get(entity).state == STATE_UNKNOWN
