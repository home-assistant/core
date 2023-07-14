"""Tests for 1-Wire switches."""
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_owproxy_mock_devices


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_switches(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for 1-Wire switches."""
    setup_owproxy_mock_devices(owproxy, Platform.SWITCH, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    setup_owproxy_mock_devices(owproxy, Platform.SWITCH, [device_id])
    # Some entities are disabled, enable them and reload before checking states
    for ent in entity_entries:
        entity_registry.async_update_entity(ent.entity_id, **{"disabled_by": None})
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.parametrize("device_id", ["05.111111111111"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_toggle(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    owproxy: MagicMock,
    device_id: str,
) -> None:
    """Test for 1-Wire switch TOGGLE service."""
    setup_owproxy_mock_devices(owproxy, Platform.SWITCH, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.05_111111111111_programmed_input_output"

    # Test TOGGLE service to off
    owproxy.return_value.read.side_effect = [b"         0"]
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Test TOGGLE service to on
    owproxy.return_value.read.side_effect = [b"         1"]
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
