"""Tests for NexBlue sensors."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueDeviceOfflineError, NexBlueError
import pytest

from homeassistant.const import PERCENTAGE
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
    assert hass.states.get("sensor.nb123456_charging_state").state == "charging"
    assert hass.states.get("sensor.nb123456_power").state == "7.2"
    assert hass.states.get("sensor.nb123456_energy").state == "1.5"
    assert hass.states.get("sensor.nb123456_network_status").state == "wifi"

    brightness = hass.states.get("sensor.nb123456_led_brightness")
    assert brightness.state == "100"
    assert brightness.attributes["unit_of_measurement"] == PERCENTAGE
    assert brightness.attributes["state_class"] == "measurement"

    device = device_registry.async_get_device(
        identifiers={("nexblue", CHARGER.serial_number)}
    )
    assert device is not None
    assert device.name == CHARGER.serial_number
    assert device.serial_number == CHARGER.serial_number

    assert (
        entity_registry.async_get_entity_id(
            "sensor", "nexblue", f"{CHARGER.serial_number}_voltage_1"
        )
        == "sensor.nb123456_voltage_l1"
    )


@pytest.mark.parametrize("error", [NexBlueDeviceOfflineError, NexBlueError])
async def test_charger_error_does_not_block_other_chargers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: type[Exception],
) -> None:
    """Test a single charger error does not prevent other chargers updating."""
    second_charger = type(CHARGER)(serial_number="NB654321")
    mock_client.async_list_chargers.return_value = [CHARGER, second_charger]
    mock_client.async_get_charger_status.side_effect = [
        CHARGER_STATUS,
        error,
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == "charging"
    assert hass.states.get("sensor.nb654321_charging_state").state == "unknown"


async def test_sensors_unavailable_when_coordinator_update_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test a failed coordinator update makes all charger entities unavailable."""
    coordinator = init_integration.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.nb123456_charging_state").state == "unavailable"
