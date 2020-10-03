"""Platform for sensor integration."""
import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_device import DevoloDeviceEntity

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAPPING = {
    "temperature": DEVICE_CLASS_TEMPERATURE,
    "light": DEVICE_CLASS_ILLUMINANCE,
    "humidity": DEVICE_CLASS_HUMIDITY,
    "current": DEVICE_CLASS_POWER,
    "total": DEVICE_CLASS_POWER,
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all sensor devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_sensor_devices:
        for multi_level_sensor in device.multi_level_sensor_property:
            entities.append(
                DevoloMultiLevelDeviceEntity(
                    homecontrol=hass.data[DOMAIN]["homecontrol"],
                    device_instance=device,
                    element_uid=multi_level_sensor,
                )
            )
    for device in hass.data[DOMAIN]["homecontrol"].devices.values():
        if hasattr(device, "consumption_property"):
            for consumption in device.consumption_property:
                for consumption_type in ["current", "total"]:
                    entities.append(
                        DevoloConsumptionEntity(
                            homecontrol=hass.data[DOMAIN]["homecontrol"],
                            device_instance=device,
                            element_uid=consumption,
                            consumption=consumption_type,
                        )
                    )
    async_add_entities(entities, False)


class DevoloMultiLevelDeviceEntity(DevoloDeviceEntity):
    """Representation of a multi level sensor within devolo Home Control."""

    def __init__(
        self,
        homecontrol,
        device_instance,
        element_uid,
        multi_level_sensor_property=None,
        sync=None,
    ):
        """Initialize a devolo multi level sensor."""
        if multi_level_sensor_property is None:
            self._multi_level_sensor_property = (
                device_instance.multi_level_sensor_property[element_uid]
            )
        else:
            self._multi_level_sensor_property = multi_level_sensor_property

        self._state = self._multi_level_sensor_property.value

        self._device_class = DEVICE_CLASS_MAPPING.get(
            self._multi_level_sensor_property.sensor_type
        )

        name = device_instance.item_name

        if self._device_class is None:
            name += f" {self._multi_level_sensor_property.sensor_type}"

        self._unit = self._multi_level_sensor_property.unit

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=name,
            sync=self._sync if sync is None else sync,
        )

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

    def _sync(self, message=None):
        """Update the multi level sensor state."""
        if message[0] == self._multi_level_sensor_property.element_uid:
            self._state = self._device_instance.multi_level_sensor_property[
                message[0]
            ].value
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()


class DevoloConsumptionEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a consumption entity within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid, consumption):
        """Initialize a devolo consumption sensor."""
        self._device_instance = device_instance

        self.value = getattr(
            device_instance.consumption_property[element_uid], consumption
        )
        self.sensor_type = consumption
        self.unit = getattr(
            device_instance.consumption_property[element_uid], f"{consumption}_unit"
        )
        self.element_uid = element_uid

        super().__init__(
            homecontrol,
            device_instance,
            element_uid,
            multi_level_sensor_property=self,
            sync=self._sync,
        )

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._unique_id}_{self.sensor_type}"

    def _sync(self, message=None):
        """Update the consumption sensor state."""
        if message[0] == self.element_uid:
            self._state = getattr(
                self._device_instance.consumption_property[self.element_uid],
                self.sensor_type,
            )
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()
