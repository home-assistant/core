"""Support for Fritzbox binary sensors."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Fritzbox binary sensor from ConfigEntry."""
    entities = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if device.has_alarm:
            entities.append(
                FritzboxBinarySensor(
                    {
                        ATTR_NAME: f"{device.name}",
                        ATTR_ENTITY_ID: f"{device.ain}",
                        ATTR_UNIT_OF_MEASUREMENT: None,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_WINDOW,
                    },
                    coordinator,
                    ain,
                )
            )

    async_add_entities(entities)


class FritzboxBinarySensor(FritzBoxEntity, BinarySensorEntity):
    """Representation of a binary Fritzbox device."""

    @property
    def is_on(self):
        """Return true if sensor is on."""
        if not self.device.present:
            return False
        return self.device.alert_state
