"""Test Satel Integra temperature sensors."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.components.satel_integra.coordinator import (
    TEMPERATURE_SENSOR_UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_ENTRY_ID, setup_integration, trigger_connection_status_update

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
async def sensor_only() -> AsyncGenerator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_sensor_not_created_by_default(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
) -> None:
    """Test temperature sensors are not created unless enabled on the zone."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_ENTRY_ID}_zones_1_temperature"
        )
        is None
    )
    mock_satel.read_temperatures.assert_not_awaited()


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_satel: AsyncMock,
    mock_config_entry_with_temperature_zone: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test temperature sensors are set up correctly."""
    await setup_integration(hass, mock_config_entry_with_temperature_zone)

    assert mock_config_entry_with_temperature_zone.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry_with_temperature_zone.entry_id,
    )

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_ENTRY_ID}_zones_1")}
    )
    assert device_entry == snapshot(name="device-zone")


async def test_temperature_sensor(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_temperature_zone: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test temperature sensors get updated correctly."""
    entity_id = "sensor.zone_temperature"

    await setup_integration(hass, mock_config_entry_with_temperature_zone)

    assert hass.states.get(entity_id).state == "21.5"
    mock_satel.read_temperatures.assert_awaited_once_with([1])

    mock_satel.read_temperatures.return_value = {1: None}
    freezer.tick(TEMPERATURE_SENSOR_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    mock_satel.read_temperatures.return_value = {1: 22.5}
    freezer.tick(TEMPERATURE_SENSOR_UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.5"


async def test_availability(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_temperature_zone: MockConfigEntry,
) -> None:
    """Test availability."""
    entity_id = "sensor.zone_temperature"

    await setup_integration(hass, mock_config_entry_with_temperature_zone)

    assert hass.states.get(entity_id).state == "21.5"

    await trigger_connection_status_update(hass, mock_satel, False)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await trigger_connection_status_update(hass, mock_satel, True)

    assert hass.states.get(entity_id).state == "21.5"
