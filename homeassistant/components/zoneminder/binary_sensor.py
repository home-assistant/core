"""Support for ZoneMinder binary sensors."""
from typing import Callable, List, Optional

from zoneminder.zm import ZoneMinder

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common import get_client_from_data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    zm_client = get_client_from_data(hass, config_entry.unique_id)
    async_add_entities([ZMAvailabilitySensor(zm_client, config_entry)])


class ZMAvailabilitySensor(BinarySensorEntity):
    """Representation of the availability of ZoneMinder as a binary sensor."""

    def __init__(self, client: ZoneMinder, config_entry: ConfigEntry):
        """Initialize availability sensor."""
        self._state = None
        self._name = config_entry.unique_id
        self._client = client
        self._config_entry = config_entry

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_availability"

    @property
    def name(self):
        """Return the name of this binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY

    def update(self):
        """Update the state of this sensor (availability of ZoneMinder)."""
        self._state = self._client.is_available
