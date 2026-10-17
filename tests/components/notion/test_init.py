"""Test Notion setup."""

from copy import deepcopy
from typing import Any

from aionotion.listener.models import ListenerKind
import pytest

from homeassistant.components.notion.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

# The id of the bridge in the bridge fixture; the sensor must reference it to link.
BRIDGE_ID = 12345
BRIDGE_HARDWARE_ID = "0x0000000000000012"
SENSOR_HARDWARE_ID = "0x0000000000000034"


@pytest.fixture(name="data_bridge")
def data_bridge_fixture(data_bridge: dict[str, Any]) -> dict[str, Any]:
    """Give the bridge a hardware id distinct from the sensor."""
    data = deepcopy(data_bridge)
    data["base_stations"][0]["hardware_id"] = BRIDGE_HARDWARE_ID
    return data


@pytest.fixture(name="data_sensor")
def data_sensor_fixture(data_sensor: dict[str, Any]) -> dict[str, Any]:
    """Link the sensor to the bridge and give it a distinct hardware id."""
    data = deepcopy(data_sensor)
    data["sensors"][0]["hardware_id"] = SENSOR_HARDWARE_ID
    data["sensors"][0]["bridge"]["id"] = BRIDGE_ID
    data["sensors"][0]["bridge"]["hardware_id"] = BRIDGE_HARDWARE_ID
    return data


@pytest.fixture(name="data_listener")
def data_listener_fixture(data_listener: dict[str, Any]) -> dict[str, Any]:
    """Use a listener kind that maps to an entity so a sensor device is created."""
    data = deepcopy(data_listener)
    data["listeners"][0]["definition_id"] = ListenerKind.HINGED_WINDOW.value
    return data


@pytest.mark.usefixtures("setup_config_entry")
async def test_device_via_device_links(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a sensor device links to its bridge via via_device_id."""
    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BRIDGE_HARDWARE_ID), config_entry.entry_id
    )
    assert bridge_device is not None

    sensor_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SENSOR_HARDWARE_ID), config_entry.entry_id
    )
    assert sensor_device is not None
    assert sensor_device.via_device_id == bridge_device.id
