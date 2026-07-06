"""Tests for the Zinvolt binary sensor."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion
from zinvolt.models import BatteryState

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
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
    with patch("homeassistant.components.zinvolt._PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_offline_battery_on_grid_unknown(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """on_grid is unknown when the battery is offline."""
    mock_zinvolt_client.get_battery_status.return_value = BatteryState.from_json(
        await async_load_fixture(hass, "current_state_offline.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("binary_sensor.zinvolt_batterij_grid_connection").state
        == STATE_UNAVAILABLE
    )
