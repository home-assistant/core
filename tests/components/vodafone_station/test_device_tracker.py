"""Define tests for the Vodafone Station device tracker."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.vodafone_station.const import SCAN_INTERVAL
from homeassistant.components.vodafone_station.coordinator import CONSIDER_HOME_SECONDS
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import DEVICE_1_HOST, DEVICE_1_MAC

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.vodafone_station.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_consider_home(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if device is considered not_home when disconnected."""
    await setup_integration(hass, mock_config_entry)

    device_tracker = f"device_tracker.{DEVICE_1_HOST}"

    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_HOME

    mock_vodafone_station_router.get_devices_data.return_value[
        DEVICE_1_MAC
    ].connected = False

    freezer.tick(SCAN_INTERVAL + CONSIDER_HOME_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_NOT_HOME
