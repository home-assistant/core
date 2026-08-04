"""Tests for NexBlue sensors."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueDeviceOfflineError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import CHARGER, CHARGER_STATUS

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test charger telemetry is exposed as sensors with unique IDs."""
    assert hass.states.get("sensor.nb123456_charging_state").state == "Charging"
    assert hass.states.get("sensor.nb123456_charging_power").state == "7.2"
    assert hass.states.get("sensor.nb123456_session_energy").state == "1.5"

    device = device_registry.async_get_device(
        identifiers={("nexblue", CHARGER.serial_number)}
    )
    assert device is not None
    assert device.name == CHARGER.serial_number

    assert (
        entity_registry.async_get_entity_id(
            "sensor", "nexblue", f"{CHARGER.serial_number}_voltage_1"
        )
        == "sensor.nb123456_voltage_l1"
    )


async def test_offline_charger_does_not_block_other_chargers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test an offline charger does not prevent healthy chargers from updating."""
    second_charger = CHARGER.__class__(serial_number="NB654321")
    mock_client.async_list_chargers.return_value = [CHARGER, second_charger]
    mock_client.async_get_charger_status.side_effect = [
        CHARGER_STATUS,
        NexBlueDeviceOfflineError,
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == "Charging"
    assert hass.states.get("sensor.nb654321_charging_state").state == "unavailable"


async def test_sensors_unavailable_when_coordinator_update_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test a failed coordinator update makes all charger entities unavailable."""
    coordinator = init_integration.runtime_data.coordinator
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == "unavailable"
