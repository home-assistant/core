"""Test for PTDevices binary sensors."""

from unittest.mock import AsyncMock, patch

from aioptdevices.interface import PTDevicesResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ptdevices.coordinator import UPDATE_INTERVAL
from homeassistant.const import Platform
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
    with patch(
        "homeassistant.components.ptdevices._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_ptdevices_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_ptdevices_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_battery_status_sensor_states(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    mock_ptdevices_level: PTDevicesResponse,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test battery status binary sensor state recognition."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await setup_integration(hass, mock_ptdevices_config_entry)

    # Make sure the battery status is "normal"
    assert (state := hass.states.get("binary_sensor.home_battery_status"))
    assert state.state == "off"

    # Set the new battery status to low
    data: PTDevicesResponse = mock_ptdevices_level
    data["body"]["C0FFEEC0FFEE"]["battery_status"] = "low"
    mock_ptdevices_interface.get_data.return_value = data

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Make sure the battery status is on (low)
    assert (state := hass.states.get("binary_sensor.home_battery_status"))
    assert state.state == "on"
