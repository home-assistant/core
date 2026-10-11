"""Test the Tesla Fleet binary sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import RESTORE_SAVE_DELAY

from . import assert_entities, assert_entities_alt, setup_platform
from .const import VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the binary sensor entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.BINARY_SENSOR])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_refresh(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the binary sensor entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.BINARY_SENSOR])

    # Refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_binary_sensor_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that a binary sensor restores persisted data when the vehicle is offline."""

    freezer.move_to("2024-01-01 00:00:00+00:00")
    await setup_platform(hass, normal_config_entry, [Platform.BINARY_SENSOR])

    # The charge cable is connected in vehicle data and absent from the product
    # payload, so this state cannot come from the empty restore store.
    assert hass.states.get("binary_sensor.test_charge_cable").state == STATE_ON

    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(RESTORE_SAVE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.tesla_fleet.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    assert hass.states.get("binary_sensor.test_charge_cable").state == STATE_ON
