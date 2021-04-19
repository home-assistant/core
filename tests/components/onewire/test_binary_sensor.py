"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.onewire.binary_sensor import DEVICE_BINARY_SENSORS
from homeassistant.setup import async_setup_component

from . import setup_onewire_patched_owserver_integration, setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import mock_registry

MOCK_BINARY_SENSORS = {
    key: value
    for (key, value) in MOCK_OWPROXY_DEVICES.items()
    if BINARY_SENSOR_DOMAIN in value
}


@pytest.mark.parametrize("device_id", MOCK_BINARY_SENSORS.keys())
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_owserver_binary_sensor(owproxy, hass, device_id):
    """Test for 1-Wire binary sensor.

    This test forces all entities to be enabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])

    mock_device = MOCK_BINARY_SENSORS[device_id]
    expected_entities = mock_device[BINARY_SENSOR_DOMAIN]

    # Force enable binary sensors
    patch_device_binary_sensors = copy.deepcopy(DEVICE_BINARY_SENSORS)
    for item in patch_device_binary_sensors[device_id[0:2]]:
        item["default_disabled"] = False

    with patch(
        "homeassistant.components.onewire.PLATFORMS", [BINARY_SENSOR_DOMAIN]
    ), patch.dict(
        "homeassistant.components.onewire.binary_sensor.DEVICE_BINARY_SENSORS",
        patch_device_binary_sensors,
    ):
        await setup_onewire_patched_owserver_integration(hass)
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
