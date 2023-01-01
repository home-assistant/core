"""Sensors provided by Homely."""
import logging

from homelypy.devices import Device, State

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .homely_device import HomelyDevice, HomelyHome

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Plate Relays as switch based on a config entry."""
    homely_home: HomelyHome = hass.data[DOMAIN][entry.entry_id]
    coordinator = homely_home.coordinator
    await coordinator.async_config_entry_first_refresh()

    entities: list[SensorEntity] = []
    for homely_device in homely_home.devices.values():
        entities.append(TemperatureEntity(coordinator, homely_device))
        entities.append(SignalStrengthEntity(coordinator, homely_device))
        entities.append(BatteryVoltageEntity(coordinator, homely_device))
    async_add_entities(entities)


class HomelySensorEntity(CoordinatorEntity, SensorEntity):
    """Abstract binary sensor class."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        homely_device: HomelyDevice,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.homely_device = homely_device
        self._attr_native_value = self.get_state_from_device(
            self.homely_device.homely_api_device
        )
        self._attr_device_info = homely_device.device_info
        self._attr_unique_id = f"{homely_device.homely_api_device.id}_{self._attr_name}"

    def get_state_from_device(self, device: Device) -> float:
        """Get the current state of the sensor."""
        return device.temperature.temperature

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device: State = next(
            filter(
                lambda device: (device.id == self.homely_device.homely_api_device.id),
                self.coordinator.location.devices,
            )
        )
        self._attr_native_value = self.get_state_from_device(device)
        self.async_write_ha_state()


class TemperatureEntity(HomelySensorEntity):
    """Represent a temperature sensor."""

    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


class SignalStrengthEntity(HomelySensorEntity):
    """Represents Zigbee signal strength."""

    _attr_name = "ZigBee signal strength"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS

    def get_state_from_device(self, device: Device) -> float:
        """Get the current state of the sensor."""
        return device.diagnostic.network_link_strength


class BatteryVoltageEntity(HomelySensorEntity):
    """Represents device battery voltage."""

    _attr_name = "Battery voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def get_state_from_device(self, device: Device) -> float:
        """Get the current state of the sensor."""
        return device.battery.voltage
