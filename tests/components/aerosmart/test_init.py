"""Tests for the aerosmart config-entry setup."""

from unittest.mock import patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockModbusApi


async def test_setup_entry_translates_shared_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A shared Modbus link conflict becomes a translated setup error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aerosmart.async_get_unit",
        side_effect=HomeAssistantError("incompatible shared connection"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "connect_failed"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "error": "incompatible shared connection"
    }


async def test_setup_entry_retries_after_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """A connect failure puts setup into its normal retry lifecycle."""
    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.aerosmart_outdoor_air_temperature") is None


async def test_setup_entry_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_api: MockModbusApi,
) -> None:
    """The entry loads and produces sensor entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_modbus_api.get_unit.call_count == 2

    outside_temp = hass.states.get("sensor.aerosmart_outdoor_air_temperature")
    assert outside_temp is not None
    assert outside_temp.state == "0.123"

    temporary_boiler_temperature = hass.states.get(
        "sensor.aerosmart_temporary_boiler_temperature"
    )
    assert temporary_boiler_temperature is not None
    assert temporary_boiler_temperature.state == "45"
    assert temporary_boiler_temperature.attributes["unit_of_measurement"] == "°C"
    assert (
        temporary_boiler_temperature.attributes["device_class"]
        == SensorDeviceClass.TEMPERATURE
    )

    heat_pump_status = hass.states.get("sensor.aerosmart_heat_pump_status")
    assert heat_pump_status is not None
    assert heat_pump_status.state == "off"
    assert heat_pump_status.attributes["options"] == [
        "restart_lockout",
        "off",
        "brine_pump_lead_time",
        "fan_lead_time",
        "opening_hot_gas_valve",
        "opening_liquid_refrigerant_valve",
        "starting_compressor",
        "minimum_runtime",
        "on",
        "pumping_down_refrigerant",
        "pumping_down_for_defrost",
        "defrosting",
        "draining_after_defrost",
    ]


async def test_unload_releases_shared_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Unloading lets Home Assistant release its shared connection holds."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_modbus_connection.connected is False
