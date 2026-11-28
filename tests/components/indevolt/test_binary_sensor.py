"""Tests for the Indevolt binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from indevolt_api import IndevoltBattery
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

METER_CONNECTED_KEY = "7120"

METER_CONNECTED_VALUE = 1000
METER_DISCONNECTED_VALUE = 1001

ENTITY_ID_GEN2 = "binary_sensor.cms_sf2000_meter_connected"

HEATING_STATE_VALUES = (
    (IndevoltBattery.MAIN_HEATING_STATE, 1, 0),
    (IndevoltBattery.PACK_1_HEATING_STATE, 1, 0),
    (IndevoltBattery.PACK_2_HEATING_STATE, 1, 0),
    (IndevoltBattery.PACK_3_HEATING_STATE, 1, 0),
    (IndevoltBattery.PACK_4_HEATING_STATE, 1, 0),
    (IndevoltBattery.PACK_5_HEATING_STATE, 1001, 1000),
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [1, 2], indirect=True)
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor entity registration and states."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_meter_connected_state_changes(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test meter_connected state transitions between ON, OFF, and unknown."""

    # Setup integration: initial value is OFF (1001)
    mock_indevolt.fetch_data.return_value[METER_CONNECTED_KEY] = (
        METER_DISCONNECTED_VALUE
    )
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
    assert state.state == STATE_OFF

    # Simulate coordinator update: value changes to ON (1000)
    mock_indevolt.fetch_data.return_value[METER_CONNECTED_KEY] = METER_CONNECTED_VALUE
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
    assert state.state == STATE_ON

    # Simulate coordinator update: value is unknown (neither ON nor OFF)
    mock_indevolt.fetch_data.return_value[METER_CONNECTED_KEY] = None
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize(("key", "on_value", "off_value"), HEATING_STATE_VALUES)
async def test_heating_state_values(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
    on_value: int,
    off_value: int,
) -> None:
    """Test the device values used for heating state binary sensors."""
    await setup_integration(hass, mock_config_entry)

    entity_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id.endswith(key)
    )

    mock_indevolt.fetch_data.return_value[key] = on_value
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == STATE_ON

    mock_indevolt.fetch_data.return_value[key] = off_value
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_binary_sensor_availability(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor availability when coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    # Simulate connection error
    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_battery_pack_heating_filtering(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
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

    # Get all binary sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Verify sensors for packs 1 and 2 exist (with SNs)
    pack1_sensors = [e for e in entity_entries if e.unique_id.endswith("9096")]
    pack2_sensors = [e for e in entity_entries if e.unique_id.endswith("9112")]

    assert len(pack1_sensors) == 1
    assert len(pack2_sensors) == 1

    # Verify sensors for packs 3, 4, and 5 don't exist (no SNs)
    pack3_sensors = [e for e in entity_entries if e.unique_id.endswith("9128")]
    pack4_sensors = [e for e in entity_entries if e.unique_id.endswith("9144")]
    pack5_sensors = [e for e in entity_entries if e.unique_id.endswith("9279")]

    assert len(pack3_sensors) == 0
    assert len(pack4_sensors) == 0
    assert len(pack5_sensors) == 0
