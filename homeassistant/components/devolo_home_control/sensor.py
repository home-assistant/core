"""Platform for sensor integration."""

from __future__ import annotations

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DevoloHomeControlConfigEntry
from .devolo_device import DevoloDeviceEntity

DEVICE_CLASS_MAPPING = {
    "battery": SensorDeviceClass.BATTERY,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "current": SensorDeviceClass.POWER,
    "total": SensorDeviceClass.ENERGY,
    "voltage": SensorDeviceClass.VOLTAGE,
}

STATE_CLASS_MAPPING = {
    "battery": SensorStateClass.MEASUREMENT,
    "temperature": SensorStateClass.MEASUREMENT,
    "light": SensorStateClass.MEASUREMENT,
    "humidity": SensorStateClass.MEASUREMENT,
    "current": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL_INCREASING,
    "voltage": SensorStateClass.MEASUREMENT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Get all sensor devices and setup them via config entry."""
    entities: list[SensorEntity] = []

    for gateway in entry.runtime_data:
        entities.extend(
            DevoloGenericMultiLevelDeviceEntity(
                homecontrol=gateway,
                device_instance=device,
                element_uid=multi_level_sensor,
            )
            for device in gateway.multi_level_sensor_devices
            for multi_level_sensor in device.multi_level_sensor_property
        )
        entities.extend(
            DevoloConsumptionEntity(
                homecontrol=gateway,
                device_instance=device,
                element_uid=consumption,
                consumption=consumption_type,
            )
            for device in gateway.devices.values()
            if hasattr(device, "consumption_property")
            for consumption in device.consumption_property
            for consumption_type in ("current", "total")
        )
        entities.extend(
            DevoloBatteryEntity(
                homecontrol=gateway,
                device_instance=device,
                element_uid=f"devolo.BatterySensor:{device.uid}",
            )
            for device in gateway.devices.values()
            if hasattr(device, "battery_level")
        )

    async_add_entities(entities)


class DevoloMultiLevelDeviceEntity(DevoloDeviceEntity, SensorEntity):
    """Abstract representation of a multi level sensor within devolo Home Control."""

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._value


class DevoloGenericMultiLevelDeviceEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a generic multi level sensor within devolo Home Control."""

    def __init__(
        self,
        homecontrol: HomeControl,
        device_instance: Zwave,
        element_uid: str,
    ) -> None:
        """Initialize a devolo multi level sensor."""
        self._multi_level_sensor_property = device_instance.multi_level_sensor_property[
            element_uid
        ]

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_device_class = DEVICE_CLASS_MAPPING.get(
            self._multi_level_sensor_property.sensor_type
        )
        self._attr_state_class = STATE_CLASS_MAPPING.get(
            self._multi_level_sensor_property.sensor_type
        )
        self._attr_native_unit_of_measurement = self._multi_level_sensor_property.unit
        self._attr_name = self._multi_level_sensor_property.sensor_type.capitalize()
        self._value = self._multi_level_sensor_property.value

        if element_uid.startswith("devolo.VoltageMultiLevelSensor:"):
            self._attr_entity_registry_enabled_default = False


class DevoloBatteryEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a battery entity within devolo Home Control."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = "Battery level"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a battery sensor."""

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._value = device_instance.battery_level


class DevoloConsumptionEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a consumption entity within devolo Home Control."""

    def __init__(
        self,
        homecontrol: HomeControl,
        device_instance: Zwave,
        element_uid: str,
        consumption: str,
    ) -> None:
        """Initialize a devolo consumption sensor."""

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._sensor_type = consumption
        self._attr_device_class = DEVICE_CLASS_MAPPING.get(consumption)
        self._attr_state_class = STATE_CLASS_MAPPING.get(consumption)
        self._attr_native_unit_of_measurement = getattr(
            device_instance.consumption_property[element_uid], f"{consumption}_unit"
        )

        self._value = getattr(
            device_instance.consumption_property[element_uid], consumption
        )

        self._attr_name = f"{consumption.capitalize()} consumption"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity.

        As both sensor types share the same element_uid we need to extend original
        self._attr_unique_id to be really unique.
        """
        return f"{self._attr_unique_id}_{self._sensor_type}"

    def _sync(self, message: tuple) -> None:
        """Update the consumption sensor state."""
        if message[0] == self._attr_unique_id:
            self._value = getattr(
                self._device_instance.consumption_property[self._attr_unique_id],
                self._sensor_type,
            )
        else:
            self._generic_message(message)
        self.schedule_update_ha_state()
