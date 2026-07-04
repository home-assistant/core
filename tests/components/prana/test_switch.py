"""Integration-style tests for Prana switches."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prana switches snapshot."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.SWITCH]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("type_key", "entity_suffix"),
    [
        ("winter", "_winter"),
        ("heater", "_heater"),
        ("auto", "_auto"),
        ("bound", "_bound"),
        ("auto_plus", "_auto_plus"),
    ],
)
async def test_switches_actions(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    type_key: str,
    entity_suffix: str,
) -> None:
    """Test turning switches on and off calls the API through the coordinator."""
    await async_init_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries
    target = f"switch.prana_recuperator{entity_suffix}"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )

    mock_prana_api.set_switch.assert_called()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: target},
        blocking=True,
    )

    assert mock_prana_api.set_switch.call_count >= 2
