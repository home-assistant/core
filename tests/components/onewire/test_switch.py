"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components.onewire.switch import DEVICE_SWITCHES
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TOGGLE, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import setup_onewire_patched_owserver_integration, setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import mock_registry

MOCK_SWITCHES = {
    key: value
    for (key, value) in MOCK_OWPROXY_DEVICES.items()
    if SWITCH_DOMAIN in value
}


@pytest.mark.parametrize("device_id", MOCK_SWITCHES.keys())
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_owserver_switch(owproxy, hass, device_id):
    """Test for 1-Wire switch.

    This test forces all entities to be enabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)

    setup_owproxy_mock_devices(owproxy, SWITCH_DOMAIN, [device_id])

    mock_device = MOCK_SWITCHES[device_id]
    expected_entities = mock_device[SWITCH_DOMAIN]

    # Force enable switches
    patch_device_switches = copy.deepcopy(DEVICE_SWITCHES)
    for item in patch_device_switches[device_id[0:2]]:
        item["default_disabled"] = False

    with patch(
        "homeassistant.components.onewire.PLATFORMS", [SWITCH_DOMAIN]
    ), patch.dict(
        "homeassistant.components.onewire.switch.DEVICE_SWITCHES", patch_device_switches
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
