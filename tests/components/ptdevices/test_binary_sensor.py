"""Test for PTDevices binary sensors."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ptdevices.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test battery status binary sensor state recognition."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await setup_integration(hass, mock_ptdevices_config_entry)

    # Make sure the battery status is "normal"
    assert (state := hass.states.get("binary_sensor.home_battery"))
    assert state.state == STATE_OFF

    # Set the new battery status to low
    mock_ptdevices_interface.get_data.return_value["body"]["C0FFEEC0FFEE"][
        "battery_status"
    ] = "low"

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Make sure the battery status is on (low)
    assert (state := hass.states.get("binary_sensor.home_battery"))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_add_remove_binary_sensor(
    hass: HomeAssistant,
    mock_ptdevices_interface: AsyncMock,
    mock_ptdevices_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling of missing and new binary sensors."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await setup_integration(hass, mock_ptdevices_config_entry)

    # Make sure the battery status exists
    assert (state := hass.states.get("binary_sensor.home_battery"))
    assert state.state != STATE_UNKNOWN

    # Remove the battery_status
    mock_ptdevices_interface.get_data.return_value["body"]["C0FFEEC0FFEE"].pop(
        "battery_status"
    )

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Make sure the battery_status is no longer present
    assert (state := hass.states.get("binary_sensor.home_battery"))
    assert state.state == STATE_UNKNOWN
