"""Support for Netgear LTE binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LTEEntity
from .const import DOMAIN
from .sensor_types import BINARY_SENSOR_CLASSES

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="mobile_connected",
        name="Mobile connected",
    ),
    BinarySensorEntityDescription(
        key="wire_connected",
        name="Wire connected",
    ),
    BinarySensorEntityDescription(
        key="roaming",
        name="Roaming",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netgear LTE binary sensor."""
    modem_data = hass.data[DOMAIN].get_modem_data(entry.data)

    async_add_entities(
        LTEBinarySensor(modem_data, description) for description in BINARY_SENSOR_TYPES
    )


class LTEBinarySensor(LTEEntity, BinarySensorEntity):
    """Netgear LTE binary sensor entity."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self.modem_data.data, self.entity_description.key)

    @property
    def device_class(self):
        """Return the class of binary sensor."""
        return BINARY_SENSOR_CLASSES[self.entity_description.key]
