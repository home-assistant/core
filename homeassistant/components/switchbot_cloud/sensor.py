"""Platform for sensor integration."""

from __future__ import annotations

from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]

    entities_to_add = []

    for device, coordinator in data.devices.sensors:
        entities_to_add.append(
            _async_make_entity(
                data.api, device, coordinator, SensorDeviceClass.TEMPERATURE
            )
        )
        entities_to_add.append(
            _async_make_entity(
                data.api, device, coordinator, SensorDeviceClass.HUMIDITY
            )
        )
        entities_to_add.append(
            _async_make_entity(data.api, device, coordinator, SensorDeviceClass.BATTERY)
        )

    async_add_entities(entities_to_add)


class SwitchBotCloudHumiditySensor(
    SwitchBotCloudEntity, CoordinatorEntity, SensorEntity
):
    """Representation of a Humidity Sensor."""

    _attr_name = "Humidity"
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._attr_native_value = self.coordinator.data.get("humidity")
            self.async_write_ha_state()


class SwitchBotCloudTemperatureSensor(
    SwitchBotCloudEntity, CoordinatorEntity, SensorEntity
):
    """Representation of a Temperature Sensor."""

    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._attr_native_value = self.coordinator.data.get("temperature")
            self.async_write_ha_state()


class SwitchBotCloudBatterySensor(
    SwitchBotCloudEntity, CoordinatorEntity, SensorEntity
):
    """Representation of a Battery Sensor."""

    _attr_name = "Battery"
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self._attr_native_value = self.coordinator.data.get("battery")
            self.async_write_ha_state()


@callback
def _async_make_entity(
    api: SwitchBotAPI,
    device: Device,
    coordinator: SwitchBotCoordinator,
    device_class: SensorDeviceClass,
) -> SensorEntity:
    """Make a SwitchBotCloud Sensor."""
    if device_class == SensorDeviceClass.TEMPERATURE:
        return SwitchBotCloudTemperatureSensor(api, device, coordinator, "temperature")
    if device_class == SensorDeviceClass.HUMIDITY:
        return SwitchBotCloudHumiditySensor(api, device, coordinator, "humidity")
    if device_class == SensorDeviceClass.BATTERY:
        return SwitchBotCloudBatterySensor(api, device, coordinator, "battery")
