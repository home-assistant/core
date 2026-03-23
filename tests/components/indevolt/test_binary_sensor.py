"""Tests for the Indevolt binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

METER_CONNECTED_KEY = "7120"
METER_CONNECTED_VALUE = 1000
METER_DISCONNECTED_VALUE = 1001

ENTITY_ID_GEN2 = "binary_sensor.cms_sf2000_meter_connected"
ENTITY_ID_GEN1 = "binary_sensor.bk1600_meter_connected"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2, 1], indirect=True)
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
@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_meter_connected_on_state(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test meter_connected reports ON when value is 1000 (Enable)."""
    mock_indevolt.fetch_data.return_value[METER_CONNECTED_KEY] = METER_CONNECTED_VALUE

    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify updated state (available)
    assert (state := hass.states.get(ENTITY_ID_GEN1)) is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_meter_connected_off_state(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test meter_connected reports OFF when value is 1001 (Disable)."""
    mock_indevolt.fetch_data.return_value[METER_CONNECTED_KEY] = (
        METER_DISCONNECTED_VALUE
    )

    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify updated state (unavailable)
    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
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
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify initial state (available)
    assert (state := hass.states.get(ENTITY_ID_GEN2)) is not None
    assert state.state == STATE_OFF

    # Simulate a fetch error
    mock_indevolt.fetch_data.side_effect = ConnectionError
    freezer.tick(delta=timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify updated state (unavailable)
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

    # Get all sensor entities
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Verify sensors for packs 1 and 2 exist (with SNs)
    pack1_sensors = [e for e in entity_entries if "9096" in e.unique_id]
    pack2_sensors = [e for e in entity_entries if "9112" in e.unique_id]

    assert len(pack1_sensors) == 1
    assert len(pack2_sensors) == 1

    # Verify sensors for packs 3, 4, and 5 don't exist (no SNs)
    pack3_sensors = [e for e in entity_entries if "9128" in e.unique_id]
    pack4_sensors = [e for e in entity_entries if "9144" in e.unique_id]
    pack5_sensors = [e for e in entity_entries if "9279" in e.unique_id]

    assert len(pack3_sensors) == 0
    assert len(pack4_sensors) == 0
    assert len(pack5_sensors) == 0
