"""Tests for the Indevolt sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from indevolt_api import (
    IndevoltBattery,
    IndevoltConfig,
    IndevoltEnergyMode,
    IndevoltSystem,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2, 1], indirect=True)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor registration for sensors."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_sensor_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor availability / non-availability."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.cms_sf2000_battery_soc"))
    assert state.state == "92"

    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.cms_sf2000_battery_soc"))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_realtime_sensor_energy_mode_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test real-time sensors are only available in real-time control energy mode."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Default fixture is not in RT mode (1), sensors should be unavailable
    assert (
        hass.states.get("sensor.cms_sf2000_real_time_mode").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.cms_sf2000_real_time_target_soc").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.cms_sf2000_real_time_power_limit").state
        == STATE_UNAVAILABLE
    )

    # Switch to RT mode (4), sensors should be available
    mock_indevolt.fetch_data.return_value[IndevoltConfig.READ_ENERGY_MODE] = (
        IndevoltEnergyMode.REAL_TIME_CONTROL
    )
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.cms_sf2000_real_time_mode").state == "standby"
    assert hass.states.get("sensor.cms_sf2000_real_time_target_soc").state == "80"
    assert hass.states.get("sensor.cms_sf2000_real_time_power_limit").state == "200"

    # Switch back to a non-RT mode (0), sensors become unavailable again
    mock_indevolt.fetch_data.return_value[IndevoltConfig.READ_ENERGY_MODE] = (
        IndevoltEnergyMode.OUTDOOR_PORTABLE
    )
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.cms_sf2000_real_time_mode").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.cms_sf2000_real_time_target_soc").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.cms_sf2000_real_time_power_limit").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_inverter_sensor_temperature_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test inverter sensors are only available when temperature is reported."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Default fixture reports a valid temperature (35.2) with heating off, sensor should be available
    assert hass.states.get("sensor.bk1600_inverter_temperature").state == "35.2"

    # Set temperature to 0 with heating off - sensor should become unavailable
    mock_indevolt.fetch_data.return_value[
        IndevoltBattery.GEN_1_INVERTER_TEMPERATURE
    ] = 0

    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.bk1600_inverter_temperature").state == STATE_UNAVAILABLE
    )

    # Switch heating on, sensor should be available again with value 0
    mock_indevolt.fetch_data.return_value[IndevoltSystem.HEATING_STATE] = 1000
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bk1600_inverter_temperature").state == "0"


# In individual tests, you can override the mock behavior
async def test_battery_pack_filtering(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that battery pack sensors are filtered based on SN availability."""

    # Mock battery pack data - only first two packs have SNs
    mock_indevolt.fetch_data.return_value = {
        "9032": "BAT001",
        "9051": "BAT002",
        "9070": None,
        "9165": "",
        "9218": None,
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get all sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Verify sensors for packs 1 and 2 exist (with SNs)
    pack1_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in ("9032", "9016", "9030", "9020", "19173"))
    ]
    pack2_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in ("9051", "9035", "9049", "9039", "19174"))
    ]

    assert len(pack1_sensors) == 5
    assert len(pack2_sensors) == 5

    # Verify sensors for packs 3, 4, and 5 don't exist (no SNs)
    pack3_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in ("9070", "9054", "9068", "9058", "19175"))
    ]
    pack4_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in ("9165", "9149", "9163", "9153", "19176"))
    ]
    pack5_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in ("9218", "9202", "9216", "9206", "19177"))
    ]

    assert len(pack3_sensors) == 0
    assert len(pack4_sensors) == 0
    assert len(pack5_sensors) == 0


async def test_battery_pack_filtering_fetch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery pack filtering when fetch fails."""

    # Mock fetch_data to raise error on battery pack SN fetch
    mock_indevolt.fetch_data.side_effect = HomeAssistantError("Timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get all sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Verify sensors (no sensors)
    battery_pack_keys = [
        "9032",
        "9051",
        "9070",
        "9165",
        "9218",
        "9016",
        "9035",
        "9054",
        "9149",
        "9202",
    ]
    battery_sensors = [
        e
        for e in entity_entries
        if any(key in e.unique_id for key in battery_pack_keys)
    ]

    assert len(battery_sensors) == 0
