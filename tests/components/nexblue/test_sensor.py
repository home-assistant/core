"""Tests for NexBlue sensors."""

from unittest.mock import MagicMock

from nexblue_api import NexBlueDeviceOfflineError, NexBlueError
import pytest

from homeassistant.components.nexblue.sensor import (
    NexBlueStatusSensor,
    _bool_text,
    _sensor_icon,
)
from homeassistant.components.sensor import SensorStateClass
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


@pytest.mark.parametrize("error", [NexBlueDeviceOfflineError, NexBlueError])
async def test_charger_error_does_not_block_other_chargers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: type[Exception],
) -> None:
    """Test a single charger error does not prevent other chargers updating."""
    second_charger = CHARGER.__class__(serial_number="NB654321")
    mock_client.async_list_chargers.return_value = [CHARGER, second_charger]
    mock_client.async_get_charger_status.side_effect = [
        CHARGER_STATUS,
        error,
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


async def test_sensor_handles_missing_values_and_brightness_metadata(
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor fallback values and brightness metadata."""
    coordinator = init_integration.runtime_data.coordinator

    brightness_sensor = NexBlueStatusSensor(
        coordinator, CHARGER.serial_number, "brightness"
    )
    assert brightness_sensor.native_unit_of_measurement == PERCENTAGE
    assert brightness_sensor.state_class is SensorStateClass.MEASUREMENT
    assert brightness_sensor.icon == "mdi:brightness-percent"

    assert (
        NexBlueStatusSensor(coordinator, CHARGER.serial_number, "current").native_value
        is None
    )
    assert (
        NexBlueStatusSensor(
            coordinator, CHARGER.serial_number, "voltage", phase=3
        ).native_value
        is None
    )

    coordinator.data[CHARGER.serial_number] = None
    assert brightness_sensor.native_value is None
    assert _bool_text(None, true_text="Enabled", false_text="Disabled") is None
    assert _sensor_icon("unknown") is None
