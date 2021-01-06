"""Tests for 1-Wire devices connected on OWServer."""
import copy
from unittest.mock import patch

from pyownet.protocol import Error as ProtocolError
import pytest

from homeassistant.components.onewire.switch import DEVICE_SWITCHES
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TOGGLE, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from . import setup_onewire_patched_owserver_integration

from tests.common import mock_registry

MOCK_DEVICE_SENSORS = {
    "12.111111111111": {
        "inject_reads": [
            b"DS2406",  # read device type
        ],
        SWITCH_DOMAIN: [
            {
                "entity_id": "switch.12_111111111111_pio_a",
                "unique_id": "/12.111111111111/PIO.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_pio_b",
                "unique_id": "/12.111111111111/PIO.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_latch_a",
                "unique_id": "/12.111111111111/latch.A",
                "injected_value": b"    1",
                "result": STATE_ON,
                "unit": None,
                "class": None,
                "disabled": True,
            },
            {
                "entity_id": "switch.12_111111111111_latch_b",
                "unique_id": "/12.111111111111/latch.B",
                "injected_value": b"    0",
                "result": STATE_OFF,
                "unit": None,
                "class": None,
                "disabled": True,
            },
        ],
    }
}


@pytest.mark.parametrize("device_id", ["12.111111111111"])
@patch("homeassistant.components.onewire.onewirehub.protocol.proxy")
async def test_owserver_switch(owproxy, hass, device_id):
    """Test for 1-Wire switch.

    This test forces all entities to be enabled.
    """
    await async_setup_component(hass, "persistent_notification", {})
    entity_registry = mock_registry(hass)

    mock_device_sensor = MOCK_DEVICE_SENSORS[device_id]

    device_family = device_id[0:2]
    dir_return_value = [f"/{device_id}/"]
    read_side_effect = [device_family.encode()]
    if "inject_reads" in mock_device_sensor:
        read_side_effect += mock_device_sensor["inject_reads"]

    expected_sensors = mock_device_sensor[SWITCH_DOMAIN]
    for expected_sensor in expected_sensors:
        read_side_effect.append(expected_sensor["injected_value"])

    # Ensure enough read side effect
    read_side_effect.extend([ProtocolError("Missing injected value")] * 10)
    owproxy.return_value.dir.return_value = dir_return_value
    owproxy.return_value.read.side_effect = read_side_effect

    # Force enable switches
    patch_device_switches = copy.deepcopy(DEVICE_SWITCHES)
    for item in patch_device_switches[device_family]:
        item["default_disabled"] = False

    with patch(
        "homeassistant.components.onewire.SUPPORTED_PLATFORMS", [SWITCH_DOMAIN]
    ), patch.dict(
        "homeassistant.components.onewire.switch.DEVICE_SWITCHES", patch_device_switches
    ):
        await setup_onewire_patched_owserver_integration(hass)
        await hass.async_block_till_done()

    assert len(entity_registry.entities) == len(expected_sensors)

    for expected_sensor in expected_sensors:
        entity_id = expected_sensor["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]

        if state.state == STATE_ON:
            owproxy.return_value.read.side_effect = [b"         0"]
            expected_sensor["result"] = STATE_OFF
        elif state.state == STATE_OFF:
            owproxy.return_value.read.side_effect = [b"         1"]
            expected_sensor["result"] = STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == expected_sensor["result"]
        assert state.attributes["device_file"] == expected_sensor.get(
            "device_file", registry_entry.unique_id
        )
