"""Velbus switch platform tests."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_entity_id, init_integration


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_disabled(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_relay: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabled switch entity."""
    # make sure the valbuasio channel is_connected method returns false
    mock_relay.is_connected.return_value = False

    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.SWITCH]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_on_off(
    hass: HomeAssistant,
    mock_relay: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switching relay on and off press."""
    await init_integration(hass, config_entry)
    entity_id = get_entity_id(entity_registry, SWITCH_DOMAIN, "qwerty123-55")
    # turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_relay.turn_off.assert_called_once_with()
    # turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_relay.turn_on.assert_called_once_with()
