"""Tests for 1-Wire devices connected on OWServer."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    SERVICE_TOGGLE,
    STATE_OFF,
    STATE_ON,
)
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
    with patch("homeassistant.components.onewire.PLATFORMS", [SWITCH_DOMAIN]):
        yield


async def test_owserver_switch(
    hass: HomeAssistant, config_entry: ConfigEntry, owproxy: MagicMock, device_id: str
):
    """Test for 1-Wire switch.

    This test forces all entities to be enabled.
    """
    entity_registry = mock_registry(hass)

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(SWITCH_DOMAIN, [])

    setup_owproxy_mock_devices(owproxy, SWITCH_DOMAIN, [device_id])
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

    setup_owproxy_mock_devices(owproxy, SWITCH_DOMAIN, [device_id])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == expected_entity[ATTR_STATE]

        if state.state == STATE_ON:
            owproxy.return_value.read.side_effect = [b"         0"]
            expected_entity[ATTR_STATE] = STATE_OFF
        elif state.state == STATE_OFF:
            owproxy.return_value.read.side_effect = [b"         1"]
            expected_entity[ATTR_STATE] = STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == expected_entity[ATTR_STATE]
        assert state.attributes[ATTR_DEVICE_FILE] == expected_entity.get(
            ATTR_DEVICE_FILE, registry_entry.unique_id
        )
