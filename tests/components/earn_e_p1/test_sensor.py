"""Tests for the EARN-E P1 Meter sensor platform."""

from unittest.mock import MagicMock

from earn_e_p1 import PacketType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_DATA, trigger_callback

from tests.common import MockConfigEntry, snapshot_platform

# The meter alternates between a realtime packet holding the instantaneous
# values and a heartbeat packet holding the meter totals. Each type only
# carries the keys the meter itself supports, so a single-phase meter never
# sends the L2/L3 keys and an electricity-only meter never sends gas.
REALTIME_3PHASE = {
    "power_delivered": 0.35,
    "power_returned": 0.0,
    "voltage_l1": 232.0,
    "voltage_l2": 231.4,
    "voltage_l3": 230.8,
    "current_l1": 2.0,
    "current_l2": 1.5,
    "current_l3": 1.1,
}
REALTIME_1PHASE = {
    "power_delivered": 0.35,
    "power_returned": 0.0,
    "voltage_l1": 232.0,
    "current_l1": 2.0,
}
HEARTBEAT_NO_GAS = {
    "energy_delivered_tariff1": 12345.678,
    "energy_delivered_tariff2": 6789.012,
    "energy_returned_tariff1": 100.0,
    "energy_returned_tariff2": 50.0,
    "wifiRSSI": -65,
}
HEARTBEAT = {**HEARTBEAT_NO_GAS, "gas_delivered": 1234.567}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor platform with snapshot assertions."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_entity_not_created_when_key_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test that entities are not created for keys missing from data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No entities should exist before first data callback
    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is None

    trigger_callback(mock_listener, device_data={"power_delivered": 1.0})
    await hass.async_block_till_done()

    # power_imported should exist (key power_delivered is in data)
    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is not None
    assert state.state == "1.0"

    # power_exported should NOT exist (key power_returned not in data)
    state = hass.states.get("sensor.earn_e_p1_meter_power_exported")
    assert state is None


async def test_sensors_added_when_key_appears_in_later_packet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are added when their key first appears in a later packet."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(
        mock_listener,
        device_data=REALTIME_3PHASE,
        seen_packet_types={PacketType.REALTIME},
    )
    await hass.async_block_till_done()

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == len(REALTIME_3PHASE)
    assert hass.states.get("sensor.earn_e_p1_meter_energy_imported_tariff_1") is None
    assert hass.states.get("sensor.earn_e_p1_meter_gas_consumed") is None

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == len(MOCK_DEVICE_DATA)

    energy = hass.states.get("sensor.earn_e_p1_meter_energy_imported_tariff_1")
    assert energy is not None
    assert energy.state == "12345.678"

    gas = hass.states.get("sensor.earn_e_p1_meter_gas_consumed")
    assert gas is not None
    assert gas.state == "1234.567"


@pytest.mark.parametrize(
    ("realtime", "heartbeat", "absent_entity_ids"),
    [
        pytest.param(
            REALTIME_1PHASE,
            HEARTBEAT,
            [
                "sensor.earn_e_p1_meter_voltage_phase_2",
                "sensor.earn_e_p1_meter_voltage_phase_3",
                "sensor.earn_e_p1_meter_current_phase_2",
                "sensor.earn_e_p1_meter_current_phase_3",
            ],
            id="single_phase_meter",
        ),
        pytest.param(
            REALTIME_3PHASE,
            HEARTBEAT_NO_GAS,
            ["sensor.earn_e_p1_meter_gas_consumed"],
            id="no_gas_meter",
        ),
    ],
)
async def test_unsupported_keys_never_create_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
    realtime: dict[str, float],
    heartbeat: dict[str, float],
    absent_entity_ids: list[str],
) -> None:
    """Test keys a meter never sends do not become entities."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(
        mock_listener,
        device_data=realtime,
        seen_packet_types={PacketType.REALTIME},
    )
    await hass.async_block_till_done()

    trigger_callback(mock_listener, device_data={**realtime, **heartbeat})
    await hass.async_block_till_done()

    for entity_id in absent_entity_ids:
        assert hass.states.get(entity_id) is None

    # Counted from the registry rather than the state machine, because the
    # Wi-Fi RSSI sensor is disabled by default and so has no state.
    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == len(realtime) + len(heartbeat)

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    # Both packet types have been seen, so the setup listener unsubscribed and
    # a packet carrying the unsupported keys can no longer add them.
    for entity_id in absent_entity_ids:
        assert hass.states.get(entity_id) is None


async def test_unload_after_all_sensors_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test unloading after every sensor has been added.

    Once all described keys have been seen, the setup listener unsubscribes
    itself; unloading afterwards must not attempt a second unsubscribe.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_wifi_rssi_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that Wi-Fi RSSI sensor is disabled by default."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    entry = entity_registry.async_get("sensor.earn_e_p1_meter_wi_fi_rssi")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
