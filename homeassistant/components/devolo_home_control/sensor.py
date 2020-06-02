"""Platform for sensor integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_sensor import DevoloDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all binary sensor and multi level sensor devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].binary_sensor_devices:
        for binary_sensor in device.binary_sensor_property:
            entities.append(
                DevoloBinaryDeviceEntity(
                    homecontrol=hass.data[DOMAIN]["homecontrol"],
                    device_instance=device,
                    element_uid=binary_sensor,
                )
            )

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_sensor_devices:
        for multi_level_sensor in device.multi_level_sensor_property:
            entities.append(
                DevoloMultiLevelDeviceEntity(
                    homecontrol=hass.data[DOMAIN]["homecontrol"],
                    device_instance=device,
                    element_uid=multi_level_sensor,
                )
            )
    async_add_entities(entities, False)


class DevoloBinaryDeviceEntity(DevoloDeviceEntity, BinarySensorEntity):
    """Representation of a binary sensor within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo binary sensor."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=device_instance.itemName
            + " "
            + device_instance.binary_sensor_property.get(element_uid).sub_type
            if device_instance.binary_sensor_property.get(element_uid).sub_type != ""
            else device_instance.itemName
            + " "
            + device_instance.binary_sensor_property.get(element_uid).sensor_type,
            sync=self.sync,
        )

        self._binary_sensor_property = self._device_instance.binary_sensor_property.get(
            self._unique_id
        )

        self._state = self._binary_sensor_property.state

        self._subscriber = None

    @property
    def is_on(self):
        """Return the state."""
        return self._state

    def sync(self, message=None):
        """Update the binary switch state and consumption."""
        if message[0].startswith("devolo.BinarySensor"):
            self._state = self._device_instance.binary_sensor_property[message[0]].state
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received")
            _LOGGER.debug(message)
        self.async_schedule_update_ha_state()


class DevoloMultiLevelDeviceEntity(DevoloDeviceEntity):
    """Representation of a multi level sensor within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo multi level sensor."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=device_instance.itemName
            + " "
            + device_instance.multi_level_sensor_property.get(element_uid).sensor_type,
            sync=self.sync,
        )

        self._state = self._device_instance.multi_level_sensor_property.get(
            element_uid
        ).value

        self.property = device_instance.multi_level_sensor_property.get(element_uid)
        if self.property.sensor_type == "temperature":
            self._device_class = DEVICE_CLASS_TEMPERATURE
            self._unit = "°C"
        elif self.property.sensor_type == "light":
            self._device_class = DEVICE_CLASS_ILLUMINANCE
            if self.property.unit == 1:
                self._unit = "lux"
            elif self.property.unit == 0:
                self._unit = "%"
            else:
                self._unit = None
        elif self.property.sensor_type == "humidity":
            self._device_class = DEVICE_CLASS_HUMIDITY
            self._unit = "%"
        else:
            self._device_class = None
            self._unit = None

    @property
    def device_class(self) -> str:
        """Return device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit

    def sync(self, message=None):
        """Update the binary switch state and consumption."""
        if message[0].startswith("devolo.MultiLevelSensor"):
            self._state = self._device_instance.multi_level_sensor_property[
                message[0]
            ].value
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received")
            _LOGGER.debug(message)
        self.async_schedule_update_ha_state()
