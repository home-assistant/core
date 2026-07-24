"""Test for PTDevices sensors."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ptdevices.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.ptdevices._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_ptdevices_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_ptdevices_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_add_remove_sensor(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling of missing and new sensors."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await setup_integration(hass, mock_ptdevices_config_entry)

    # Make sure the status exists
    assert (state := hass.states.get("sensor.home_status"))
    assert state.state != STATE_UNKNOWN

    # Remove the status
    mock_ptdevices_interface.get_data.return_value["body"]["C0FFEEC0FFEE"].pop("status")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Make sure the status is no longer present
    assert (state := hass.states.get("sensor.home_status"))
    assert state.state == STATE_UNKNOWN
