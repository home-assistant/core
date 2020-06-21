"""Platform for binary sensor integration."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_device import DevoloDeviceEntity

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

    async_add_entities(entities, False)


class DevoloBinaryDeviceEntity(DevoloDeviceEntity, BinarySensorEntity):
    """Representation of a binary sensor within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo binary sensor."""
        if device_instance.binary_sensor_property.get(element_uid).sub_type != "":
            name = f"{device_instance.itemName} {device_instance.binary_sensor_property.get(element_uid).sub_type}"
        else:
            name = f"{device_instance.itemName} {device_instance.binary_sensor_property.get(element_uid).sensor_type}"

        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
            name=name,
            sync=self._sync,
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

    def _sync(self, message=None):
        """Update the binary sensor state."""
        if message[0].startswith("devolo.BinarySensor"):
            self._state = self._device_instance.binary_sensor_property[message[0]].state
        elif message[0].startswith("hdm"):
            self._available = self._device_instance.is_online()
        else:
            _LOGGER.debug("No valid message received: %s", message)
        self.schedule_update_ha_state()
