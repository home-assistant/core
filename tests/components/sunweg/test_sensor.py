"""Tests for the Sun WEG sensor."""

from unittest.mock import MagicMock

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.components.sunweg.const import DeviceType
from homeassistant.components.sunweg.coordinator import SunWEGDataUpdateCoordinator
from homeassistant.components.sunweg.sensor import SunWEGInverter
from homeassistant.components.sunweg.sensor_types.sensor_entity_description import (
    SunWEGSensorEntityDescription,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant


async def test_sensor_static_metric(hass: HomeAssistant, plant_fixture) -> None:
    """Test sensor update with static metric."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    description = SunWEGSensorEntityDescription(
        key="kwh_per_kwp",
        name="kWh por kWp",
        api_variable_key="kwh_per_kwp",
    )
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )

    sensor = SunWEGInverter(
        name=f"{plant_fixture.name} Total",
        unique_id=f"{coordinator.plant_id}-{description.key}",
        coordinator=coordinator,
        description=description,
        device_type=DeviceType.TOTAL,
    )
    await coordinator.async_refresh()
    sensor.async_write_ha_state = MagicMock()
    sensor._handle_coordinator_update()
    assert sensor.native_value == plant_fixture.kwh_per_kwp


async def test_sensor_dynamic_metric(hass: HomeAssistant, plant_fixture) -> None:
    """Test sensor update with dynamic metric."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    description = SunWEGSensorEntityDescription(
        key="total_energy_today",
        name="Energy Today",
        api_variable_key="today_energy",
        api_variable_unit="today_energy_metric",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    sensor = SunWEGInverter(
        name=f"{plant_fixture.name} Total",
        unique_id=f"{coordinator.plant_id}-{description.key}",
        coordinator=coordinator,
        description=description,
        device_type=DeviceType.TOTAL,
    )
    await coordinator.async_refresh()
    sensor.async_write_ha_state = MagicMock()
    sensor._handle_coordinator_update()
    assert sensor.native_value == plant_fixture.today_energy
    assert sensor.native_unit_of_measurement == plant_fixture.today_energy_metric
    assert sensor.native_unit_of_measurement != UnitOfEnergy.WATT_HOUR


async def test_sensor_never_reset(
    hass: HomeAssistant,
    plant_fixture,
    plant_fixture_total_power_0,
    plant_fixture_total_power_none,
) -> None:
    """Test sensor update with dynamic metric."""
    api = MagicMock()
    api.plant = MagicMock(return_value=plant_fixture)
    api.complete_inverter = MagicMock()
    description = SunWEGSensorEntityDescription(
        key="total_energy_output",
        name="Lifetime energy output",
        api_variable_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        never_resets=True,
    )
    coordinator = SunWEGDataUpdateCoordinator(
        hass, api, plant_fixture.id, plant_fixture.name
    )
    sensor = SunWEGInverter(
        name=f"{plant_fixture.name} Total",
        unique_id=f"{coordinator.plant_id}-{description.key}",
        coordinator=coordinator,
        description=description,
        device_type=DeviceType.TOTAL,
    )
    sensor.async_write_ha_state = MagicMock()

    await coordinator.async_refresh()
    sensor._handle_coordinator_update()
    assert sensor.native_value == plant_fixture.total_energy

    coordinator.data = plant_fixture_total_power_0
    sensor._handle_coordinator_update()
    assert sensor.native_value is not None
    assert sensor.native_value == plant_fixture.total_energy

    coordinator.data = plant_fixture_total_power_none
    sensor._handle_coordinator_update()
    assert sensor.native_value != 0.0
    assert sensor.native_value == plant_fixture.total_energy
