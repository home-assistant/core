"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.onewire.binary_sensor import DEVICE_BINARY_SENSORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import mock_registry


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [BINARY_SENSOR_DOMAIN]):
        yield


async def test_owserver_binary_sensor(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock, device_id: str
):
    """Test for 1-Wire binary sensor.

    This test forces all entities to be enabled.
    """
    entity_registry = mock_registry(hass)

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(BINARY_SENSOR_DOMAIN, [])

    # Force enable binary sensors
    patch_device_binary_sensors = copy.deepcopy(DEVICE_BINARY_SENSORS)
    if device_binary_sensor := patch_device_binary_sensors.get(device_id[0:2]):
        for item in device_binary_sensor:
            item.entity_registry_enabled_default = True

    with patch.dict(
        "homeassistant.components.onewire.binary_sensor.DEVICE_BINARY_SENSORS",
        patch_device_binary_sensors,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        state = hass.states.get(entity_id)
        assert state.state == expected_entity["result"]
        assert state.attributes["device_file"] == expected_entity.get(
            "device_file", registry_entry.unique_id
        )
