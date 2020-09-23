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
                DevoloGenericMultiLevelDeviceEntity(
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
    """Abstract representation of a multi level sensor within devolo Home Control."""

    @property
    def device_class(self) -> str:
        """Return device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit


class DevoloGenericMultiLevelDeviceEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a generic multi level sensor within devolo Home Control."""

    def __init__(
        self,
        homecontrol,
        device_instance,
        element_uid,
    ):
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


class DevoloConsumptionEntity(DevoloMultiLevelDeviceEntity):
    """Representation of a consumption entity within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid, consumption):
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
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._unique_id}_{self._sensor_type}"

    def _sync(self, message):
        """Update the consumption sensor state."""
        if message[0] == self._unique_id:
            self._value = getattr(
                self._device_instance.consumption_property[self._unique_id],
                self._sensor_type,
            )
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()
