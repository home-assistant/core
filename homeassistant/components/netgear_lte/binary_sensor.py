"""Support for Netgear LTE binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LTEEntity
from .sensor_types import ALL_BINARY_SENSORS, BINARY_SENSOR_CLASSES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netgear LTE binary sensor."""
    modem_data = hass.data[DOMAIN].get_modem_data(entry.data)

    async_add_entities(
        LTEBinarySensor(modem_data, sensor) for sensor in ALL_BINARY_SENSORS
    )


class LTEBinarySensor(LTEEntity, BinarySensorEntity):
    """Netgear LTE binary sensor entity."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self.modem_data.data, self.sensor_type)

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return BINARY_SENSOR_CLASSES[self.sensor_type]
