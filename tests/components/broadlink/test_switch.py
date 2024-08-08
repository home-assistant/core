"""Tests for Broadlink switches."""

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device


async def test_switch_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful setup with a switch."""
    device = get_device("Dining room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    switches = [entry for entry in entries if entry.domain == Platform.SWITCH]
    assert len(switches) == 4

    for slot, switch in enumerate(switches):
        assert (
            hass.states.get(switch.entity_id).attributes[ATTR_FRIENDLY_NAME]
            == f"{device.name} S{slot+1}"
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

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
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
