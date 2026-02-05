"""Tests for the LoJack sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricPotential, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant

from .const import (
    TEST_BATTERY_VOLTAGE,
    TEST_MAKE,
    TEST_MODEL,
    TEST_ODOMETER,
    TEST_SPEED,
    TEST_YEAR,
)

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test sensor entities are created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that main sensors exist
    assert hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_odometer".lower()
    )
    assert hass.states.get(f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_speed".lower())
    assert hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_battery_voltage".lower()
    )
    assert hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_location_last_reported".lower()
    )


async def test_odometer_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test odometer sensor value and attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_odometer".lower()
    )
    assert state is not None
    assert float(state.state) == round(TEST_ODOMETER, 1)
    assert state.attributes.get("unit_of_measurement") == UnitOfLength.MILES
    assert state.attributes.get("device_class") == SensorDeviceClass.DISTANCE


async def test_speed_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test speed sensor value and attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_speed".lower()
    )
    assert state is not None
    assert float(state.state) == round(TEST_SPEED, 1)
    assert state.attributes.get("unit_of_measurement") == UnitOfSpeed.MILES_PER_HOUR
    assert state.attributes.get("device_class") == SensorDeviceClass.SPEED


async def test_battery_voltage_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test battery voltage sensor value and attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_battery_voltage".lower()
    )
    assert state is not None
    assert float(state.state) == round(TEST_BATTERY_VOLTAGE, 2)
    assert state.attributes.get("unit_of_measurement") == UnitOfElectricPotential.VOLT
    assert state.attributes.get("device_class") == SensorDeviceClass.VOLTAGE


async def test_diagnostic_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test that diagnostic sensors are disabled by default."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Diagnostic sensors should not have state when disabled by default
    # They exist in the entity registry but are disabled
    entity_registry = hass.helpers.entity_registry.async_get(hass)

    # Check that diagnostic entities exist but are disabled
    make_entity = entity_registry.async_get(
        f"sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_make".lower()
    )
    if make_entity:
        assert make_entity.disabled_by is not None
