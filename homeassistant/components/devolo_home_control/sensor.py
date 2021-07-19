"""Platform for sensor integration."""
from __future__ import annotations

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devolo_device import DevoloDeviceEntity

DEVICE_CLASS_MAPPING = {
    "battery": DEVICE_CLASS_BATTERY,
    "temperature": DEVICE_CLASS_TEMPERATURE,
    "light": DEVICE_CLASS_ILLUMINANCE,
    "humidity": DEVICE_CLASS_HUMIDITY,
    "current": DEVICE_CLASS_POWER,
    "total": DEVICE_CLASS_ENERGY,
    "voltage": DEVICE_CLASS_VOLTAGE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all sensor devices and setup them via config entry."""
    entities: list[SensorEntity] = []

    for gateway in hass.data[DOMAIN][entry.entry_id]["gateways"]:
        for device in gateway.multi_level_sensor_devices:
            for multi_level_sensor in device.multi_level_sensor_property:
                entities.append(
                    DevoloGenericMultiLevelDeviceEntity(
                        homecontrol=gateway,
                        device_instance=device,
                        element_uid=multi_level_sensor,
                    )
                )
        for device in gateway.devices.values():
            if hasattr(device, "consumption_property"):
                for consumption in device.consumption_property:
                    for consumption_type in ("current", "total"):
                        entities.append(
                            DevoloConsumptionEntity(
                                homecontrol=gateway,
                                device_instance=device,
                                element_uid=consumption,
                                consumption=consumption_type,
                            )
                        )
            if hasattr(device, "battery_level"):
                entities.append(
                    DevoloBatteryEntity(
                        homecontrol=gateway,
                        device_instance=device,
                        element_uid=f"devolo.BatterySensor:{device.uid}",
                    )
                )

    async_add_entities(entities, False)


class DevoloMultiLevelDeviceEntity(DevoloDeviceEntity, SensorEntity):
    """Abstract representation of a multi level sensor within devolo Home Control."""

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self._device_class

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return self._unit


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

        self._device_class = DEVICE_CLASS_MAPPING.get(
            self._multi_level_sensor_property.sensor_type
        )

        self._value = self._multi_level_sensor_property.value
        self._unit = self._multi_level_sensor_property.unit

        if self._device_class is None:
            self._name += f" {self._multi_level_sensor_property.sensor_type}"

        if element_uid.startswith("devolo.VoltageMultiLevelSensor:"):
            self._enabled_default = False


class DevoloBatteryEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a battery entity within devolo Home Control."""

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a battery sensor."""

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._device_class = DEVICE_CLASS_MAPPING.get("battery")

        self._value = device_instance.battery_level
        self._unit = PERCENTAGE


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
        self._device_class = DEVICE_CLASS_MAPPING.get(consumption)

        self._value = getattr(
            device_instance.consumption_property[element_uid], consumption
        )
        self._unit = getattr(
            device_instance.consumption_property[element_uid], f"{consumption}_unit"
        )

        self._name += f" {consumption}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return f"{self._unique_id}_{self._sensor_type}"

    def _sync(self, message: tuple) -> None:
        """Update the consumption sensor state."""
        if message[0] == self._unique_id:
            self._value = getattr(
                self._device_instance.consumption_property[self._unique_id],
                self._sensor_type,
            )
        else:
            self._generic_message(message)
        self.schedule_update_ha_state()
