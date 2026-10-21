"""Tests for Broadlink switches."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.switch import (
    PLATFORM_SCHEMA,
    async_setup_platform,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device

IR_PACKET = (
    "JgBGAJKVETkRORA6ERQRFBEUERQRFBE5ETkQOhAVEBUQFREUEBUQ"
    "OhEUERQRORE5EBURFBA6EBUQOhE5EBUQFRA6EDoRFBEADQUAAA=="
)


async def test_switch_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful setup with a switch."""
    device = get_device("Dining room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 1

    switch = switches[0]
    assert (
        hass.states.get(switch.entity_id).attributes[ATTR_FRIENDLY_NAME] == device.name
    )
    assert hass.states.get(switch.entity_id).state == STATE_OFF
    assert mock_setup.api.auth.call_count == 1


async def test_switch_turn_off_turn_on(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test send turn on and off for a switch."""
    device = get_device("Dining room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 1

    switch = switches[0]
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": switch.entity_id},
        blocking=True,
    )
    assert hass.states.get(switch.entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": switch.entity_id},
        blocking=True,
    )
    assert hass.states.get(switch.entity_id).state == STATE_ON

    assert mock_setup.api.auth.call_count == 1


async def test_slots_switch_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful setup with a switch with slots."""
    device = get_device("Gaming room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 4

    for slot, switch in enumerate(switches):
        assert (
            hass.states.get(switch.entity_id).attributes[ATTR_FRIENDLY_NAME]
            == f"{device.name} S{slot + 1}"
        )
        assert hass.states.get(switch.entity_id).state == STATE_OFF
        assert mock_setup.api.auth.call_count == 1


async def test_slots_switch_turn_off_turn_on(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test send turn on and off for a switch with slots."""
    device = get_device("Gaming room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 4

    for switch in switches:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": switch.entity_id},
            blocking=True,
        )
        assert hass.states.get(switch.entity_id).state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": switch.entity_id},
            blocking=True,
        )
        assert hass.states.get(switch.entity_id).state == STATE_ON

        assert mock_setup.api.auth.call_count == 1


@pytest.mark.parametrize(
    "device_name", ["Entrance", "Living Room", "Office", "Garage", "Study"]
)
async def test_custom_ir_switch_setup_works(
    hass: HomeAssistant, device_name: str
) -> None:
    """Test a custom IR switch from YAML is added to each type of remote."""
    device = get_device(device_name)
    mock_setup = await device.setup_entry(hass)

    config = PLATFORM_SCHEMA(
        {
            "platform": DOMAIN,
            "mac": device.mac,
            "switches": [
                {"name": "Fan", "command_on": IR_PACKET, "command_off": IR_PACKET}
            ],
        }
    )
    await async_setup_platform(hass, config, MagicMock())
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert len(entity_ids) == 1

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": entity_ids[0]}, blocking=True
    )
    assert mock_setup.api.send_data.call_count == 1
