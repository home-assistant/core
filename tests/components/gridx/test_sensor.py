"""Tests for the gridX sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gridx.const import LIVE_UPDATE_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import SYSTEM_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_connector")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.gridx.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_subsystem_entities_added_when_data_appears(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test optional subsystem sensors are only created once their data exists."""
    full_data = mock_connector.get_live_data.return_value[SYSTEM_ID]
    mock_connector.get_live_data.return_value = {
        SYSTEM_ID: {k: v for k, v in full_data.items() if k != "battery"}
    }
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.home_pv_power") is not None
    assert hass.states.get("sensor.home_battery_state_of_charge") is None

    mock_connector.get_live_data.return_value = {SYSTEM_ID: full_data}
    freezer.tick(LIVE_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_battery_state_of_charge").state == "77.0"
