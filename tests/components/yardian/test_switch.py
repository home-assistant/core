"""Validate Yardian switch behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.yardian.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on a switch."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.yardian_smart_sprinkler_zone_1"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_yardian_client.start_irrigation.assert_called_once_with(0, 6)


async def test_turn_off_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off a switch."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.yardian_smart_sprinkler_zone_1"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_yardian_client.stop_irrigation.assert_called_once()
