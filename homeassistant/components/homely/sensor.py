"""Sensors provided by Homely."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from homelypy.devices import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import HomelyHomeCoordinator
from .homely_device import HomelyDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Plate Relays as switch based on a config entry."""
    homely_home: HomelyHomeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for homely_device in homely_home.devices.values():
        if homely_device.homely_api_device.model_name == "EMI Norwegian HAN":
            entities.extend(
                [
                    HomelySensorEntity(homely_home, homely_device, description)
                    for description in HAN_SENSOR_ENTITY_DESCRIPTIONS
                ]
            )
        else:
            entities.extend(
                [
                    HomelySensorEntity(homely_home, homely_device, description)
                    for description in GENERIC_SENSOR_TYPES
                ]
            )
    async_add_entities(entities)


@dataclass
class HomelySensorEntityDescription(SensorEntityDescription):
    """Class describing a Homely sensor entity."""

    value_fn: Callable[[Device], StateType] = lambda _: _


GENERIC_SENSOR_TYPES: tuple[HomelySensorEntityDescription, ...] = (
    HomelySensorEntityDescription(
        key="Temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature.temperature,
    ),
    HomelySensorEntityDescription(
        key="BatteryVoltage",
        name="Battery voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda device: device.battery.voltage,
    ),
    HomelySensorEntityDescription(
        key="ZigbeeSignalStrength",
        name="Zigbee signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=lambda device: device.diagnostic.network_link_strength,
    ),
)

HAN_SENSOR_ENTITY_DESCRIPTIONS: tuple[HomelySensorEntityDescription, ...] = (
    HomelySensorEntityDescription(
        key="SummationDelivered",
        name="Summation delivered",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.metering.summation_delivered / 1000,
    ),
    HomelySensorEntityDescription(
        key="SummationReceived",
        name="Summation received",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda device: device.metering.summation_received / 1000,
    ),
    HomelySensorEntityDescription(
        key="Demand",
        name="Demand",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda device: device.metering.demand / 1000,
    ),
)


class HomelySensorEntity(CoordinatorEntity, SensorEntity):
    """Homely sensor class."""

    _attr_has_entity_name = True
    entity_description: HomelySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        homely_device: HomelyDevice,
        description: HomelySensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.homely_device = homely_device
        self.entity_description = description
        self._homely_device_state: Device = self.get_homely_device_state()
        self._attr_device_info = homely_device.device_info
        self._attr_unique_id = f"{homely_device.homely_api_device.id}_{self.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self._homely_device_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._homely_device_state = self.get_homely_device_state()
        self.async_write_ha_state()

    def get_homely_device_state(self) -> Device:
        """Find my updated device."""
        return next(
            filter(
                lambda device: (device.id == self.homely_device.homely_api_device.id),
                self.coordinator.location.devices,
            )
        )
