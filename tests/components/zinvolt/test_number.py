"""Tests for the Zinvolt number."""

import json
from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion
from zinvolt.models import BatteryState

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_load_fixture, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_max_output_when_unlocked(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test max_output value stays within its own bound once output is unlocked."""
    fixture_data = json.loads(
        await async_load_fixture(hass, "current_state.json", DOMAIN)
    )
    fixture_data["globalSettings"]["maxOutputUnlocked"] = True
    mock_zinvolt_client.get_battery_status.return_value = BatteryState.from_json(
        json.dumps(fixture_data)
    )

    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.zinvolt_batterij_maximum_output")
    assert state.state == "2000"
    assert state.attributes["max"] == 2000
