"""Tests for the TRMNL sensor."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLError
from trmnl.models import Device

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_coordinator_unavailable(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that sensor entities become unavailable when the coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_trmnl_battery").state != STATE_UNAVAILABLE

    mock_trmnl_client.get_devices.side_effect = TRMNLError
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_trmnl_battery").state == STATE_UNAVAILABLE


async def test_dynamic_new_device(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new entities are added when a new device appears in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    # Initially the existing device's battery sensor has a state
    assert hass.states.get("sensor.test_trmnl_battery") is not None
    assert hass.states.get("sensor.new_trmnl_battery") is None

    # Simulate a new device appearing in the next coordinator update
    new_device = Device(
        identifier=99999,
        name="New TRMNL",
        friendly_id="ABCDEF",
        mac_address="AA:BB:CC:DD:EE:FF",
        battery_voltage=4.0,
        rssi=-70,
        sleep_mode_enabled=False,
        sleep_start_time=0,
        sleep_end_time=0,
        percent_charged=85.0,
        wifi_strength=60,
    )
    mock_trmnl_client.get_devices.return_value = [
        *mock_trmnl_client.get_devices.return_value,
        new_device,
    ]
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.new_trmnl_battery") is not None
