"""Tests for 1-Wire devices connected on OWServer."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_STATE
from homeassistant.core import HomeAssistant

from . import setup_owproxy_mock_devices
from .const import (
    ATTR_DEFAULT_DISABLED,
    ATTR_DEVICE_FILE,
    ATTR_UNIQUE_ID,
    MOCK_OWPROXY_DEVICES,
)

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

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(BINARY_SENSOR_DOMAIN, [])

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_entities)

    # Ensure all entities are enabled
    for expected_entity in expected_entities:
        if expected_entity.get(ATTR_DEFAULT_DISABLED):
            entity_id = expected_entity[ATTR_ENTITY_ID]
            registry_entry = entity_registry.entities.get(entity_id)
            assert registry_entry.disabled
            assert registry_entry.disabled_by == "integration"
            entity_registry.async_update_entity(entity_id, **{"disabled_by": None})

    setup_owproxy_mock_devices(owproxy, BINARY_SENSOR_DOMAIN, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == expected_entity[ATTR_STATE]
        assert state.attributes[ATTR_DEVICE_FILE] == expected_entity.get(
            ATTR_DEVICE_FILE, registry_entry.unique_id
        )
