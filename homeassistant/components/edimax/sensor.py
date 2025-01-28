"""Support for Edimax sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.switch import HomeAssistant
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EdimaxConfigEntry
from .smartplug_adapter import SmartPlugAdapter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EdimaxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    adapter = config_entry.runtime_data
    async_add_entities(
        [
            EdimaxNowPowerSensor(adapter, config_entry.data["name"]),
            EdimaxEnergySensor(adapter, config_entry.data["name"]),
        ],
        True,
    )


class EdimaxNowPowerSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_key = "power"
    translation_key = "power"
    _attr_name = "Edimax Current Power"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_unique_id = "edimax.now_power"
    _attr_suggested_display_precision = 2
    _attr_enabled_default = True

    adapter: SmartPlugAdapter

    def __init__(self, adapter: SmartPlugAdapter, name: str) -> None:
        """Initialize the switch."""

        self.adapter = adapter
        self._name = name
        _attr_unique_id = f"{adapter.info.serial_number}_now_power"

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._attr_native_value = self.adapter.now_power


class EdimaxEnergySensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_key = "energy"
    translation_key = "energy"
    _attr_name = "Edimax Total Day Energy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_unique_id = "edimax-energy"  # f"{coordinator.info.serial_number}_energy"
    _attr_suggested_display_precision = 2
    _attr_enabled_default = True

    adapter: SmartPlugAdapter

    def __init__(self, adapter: SmartPlugAdapter, name: str) -> None:
        """Initialize the switch."""

        self.adapter = adapter
        self._name = name
        _attr_unique_id = f"edimax.{adapter.info.serial_number}_energy"

    def update(self) -> None:
        """Fetch new state data for the sensor."""

        self._attr_native_value = self.adapter.total_energy_day
