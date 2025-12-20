"""Tests for the Actron Air sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.actron_air import sensor as actron_sensor
from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.components.actron_air.coordinator import (
    ActronAirRuntimeData,
    ActronAirSystemCoordinator,
)
from homeassistant.components.actron_air.sensor import PERIPHERAL_SENSORS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockPeripheral:
    """Mock Actron Air peripheral object."""

    def __init__(self) -> None:
        """Initialize mock peripheral with default values."""
        self.serial_number = "ZC_12345"
        self.device_type = "Zone Controller"
        self.logical_address = "3"
        self.battery_level = 85
        self.humidity = 45
        self.temperature = 22.5
        self.zones = [SimpleNamespace(title="Living Room")]


async def _create_coordinator(
    hass: HomeAssistant, peripherals: list[MockPeripheral]
) -> ActronAirSystemCoordinator:
    """Create a coordinator instance backed by mocked API data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    api = MagicMock()
    api.update_status = AsyncMock()
    api.state_manager = MagicMock()

    ac_system = SimpleNamespace(
        system_name="NEO_23C04269",
        master_wc_model="NTW-100",
        master_wc_firmware_version="1.0.0",
    )

    status = SimpleNamespace(
        ac_system=ac_system,
        peripherals=peripherals,
        clean_filter=False,
        defrost_mode=False,
        compressor_chasing_temperature=24.0,
        compressor_live_temperature=23.5,
        compressor_mode="cooling",
        compressor_speed=50,
        compressor_power=1500,
        outdoor_temperature=28.5,
    )
    api.state_manager.get_status.return_value = status

    coordinator = ActronAirSystemCoordinator(
        hass,
        config_entry,
        api,
        {"serial": "NEO_23C04269"},
    )
    coordinator.data = status
    coordinator.is_device_stale = MagicMock(return_value=False)
    return coordinator


async def test_sensor_setup_creates_all_entities(
    hass: HomeAssistant,
) -> None:
    """Test that sensor setup creates all expected entities."""
    peripheral = MockPeripheral()
    coordinator = await _create_coordinator(hass, [peripheral])

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = ActronAirRuntimeData(
        api=MagicMock(),
        system_coordinators={coordinator.serial_number: coordinator},
    )

    added: list = []

    def _async_add_entities(entities):
        added.extend(entities)

    await actron_sensor.async_setup_entry(hass, entry, _async_add_entities)

    # Should create: 8 AC sensors + 3 peripheral sensors
    assert len(added) == 11

    # Verify AC system sensors
    ac_sensors = [
        entity for entity in added if isinstance(entity, actron_sensor.ActronAirSensor)
    ]
    assert len(ac_sensors) == 8

    # Verify we have the expected sensor keys
    ac_sensor_keys = {entity.entity_description.key for entity in ac_sensors}
    assert "clean_filter" in ac_sensor_keys
    assert "outdoor_temperature" in ac_sensor_keys

    # Verify peripheral sensors
    peripheral_sensors = [
        entity
        for entity in added
        if isinstance(entity, actron_sensor.ActronAirPeripheralSensorEntity)
    ]
    assert len(peripheral_sensors) == 3

    # Verify we have the expected peripheral sensor keys
    peripheral_sensor_keys = {
        entity.entity_description.key for entity in peripheral_sensors
    }
    assert "battery" in peripheral_sensor_keys
    assert "humidity" in peripheral_sensor_keys
    assert "temperature" in peripheral_sensor_keys


async def test_peripheral_battery_sensor_properties(
    hass: HomeAssistant,
) -> None:
    """Test peripheral battery sensor returns correct values."""
    peripheral = MockPeripheral()
    coordinator = await _create_coordinator(hass, [peripheral])

    battery_description = next(
        description
        for description in PERIPHERAL_SENSORS
        if description.key == "battery"
    )
    entity = actron_sensor.ActronAirPeripheralSensorEntity(
        coordinator, peripheral, battery_description
    )

    assert entity.native_value == 85
    assert entity.available is True
    assert entity.unique_id == "ZC_12345_battery"


async def test_peripheral_sensor_unavailable_when_stale(
    hass: HomeAssistant,
) -> None:
    """Test sensor becomes unavailable when device is stale."""
    peripheral = MockPeripheral()
    coordinator = await _create_coordinator(hass, [peripheral])
    coordinator.is_device_stale = MagicMock(return_value=True)

    battery_description = next(
        description
        for description in PERIPHERAL_SENSORS
        if description.key == "battery"
    )
    entity = actron_sensor.ActronAirPeripheralSensorEntity(
        coordinator, peripheral, battery_description
    )

    assert entity.available is False
