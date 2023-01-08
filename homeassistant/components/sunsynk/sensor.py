"""Support for Sunsynk sensors."""
from __future__ import annotations

from sunsynk.client import SunsynkClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SunsynkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Add a Sunsynk entry."""
    username = entry.data["username"]
    password = entry.data["password"]
    inverter_sn = entry.data["inverter_sn"]

    api = await SunsynkClient.create(username, password)

    coordinator = SunsynkCoordinator(hass, api)

    add_entities(
        [
            SunsynkGridEnergySensor(coordinator, entry.title, inverter_sn),
            SunsynkBatteryEnergySensor(coordinator, entry.title, inverter_sn),
            SunsynkSolarEnergySensor(coordinator, entry.title, inverter_sn),
        ]
    )


class SunsynkSensor(CoordinatorEntity, SensorEntity):
    """Representation of a grid power usage."""

    def __init__(self, coordinator, platform_name: str, inverter_sn: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.platform_name = platform_name
        self.inverter_sn = inverter_sn

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.inverter_sn)},
            name=f"Inverter {self.inverter_sn}",
            manufacturer="Sunsynk",
        )


class SunsynkGridEnergySensor(SunsynkSensor):
    """Representation of a grid power usage."""

    _attr_name = "Grid Power"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID."""
        return f"{self.inverter_sn}_grid_power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data["grid_energy"]
        self.async_write_ha_state()


class SunsynkBatteryEnergySensor(SunsynkSensor):
    """Representation of a battery power usage."""

    _attr_name = "Battery Power"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID."""
        return f"{self.inverter_sn}_battery_power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data["battery_energy"]
        self.async_write_ha_state()


class SunsynkSolarEnergySensor(SunsynkSensor):
    """Representation of a solar power usage."""

    _attr_name = "Solar Power"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID."""
        return f"{self.inverter_sn}_solar_power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data["solar_energy"]
        self.async_write_ha_state()
