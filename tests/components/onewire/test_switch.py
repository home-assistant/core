"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.onewire.switch import DEVICE_SWITCHES
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TOGGLE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

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

    setup_owproxy_mock_devices(owproxy, SWITCH_DOMAIN, [device_id])

    mock_device = MOCK_OWPROXY_DEVICES[device_id]
    expected_entities = mock_device.get(SWITCH_DOMAIN, [])

    # Force enable switches
    patch_device_switches = copy.deepcopy(DEVICE_SWITCHES)
    if device_switch := patch_device_switches.get(device_id[0:2]):
        for item in device_switch:
            item.entity_registry_enabled_default = True

    with patch.dict(
        "homeassistant.components.onewire.switch.DEVICE_SWITCHES", patch_device_switches
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

        if state.state == STATE_ON:
            owproxy.return_value.read.side_effect = [b"         0"]
            expected_entity["result"] = STATE_OFF
        elif state.state == STATE_OFF:
            owproxy.return_value.read.side_effect = [b"         1"]
            expected_entity["result"] = STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == expected_entity["result"]
        assert state.attributes["device_file"] == expected_entity.get(
            "device_file", registry_entry.unique_id
        )
