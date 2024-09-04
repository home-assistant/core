"""Support for Genius Hub binary_sensor devices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GeniusHubConfigEntry
from .entity import GeniusDevice

GH_STATE_ATTR = "outputOnOff"
GH_TYPE = "Receiver"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Genius Hub binary sensor entities."""

    broker = entry.runtime_data

    async_add_entities(
        GeniusBinarySensor(broker, d, GH_STATE_ATTR)
        for d in broker.client.device_objs
        if GH_TYPE in d.data["type"]
    )


class GeniusBinarySensor(GeniusDevice, BinarySensorEntity):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, broker, device, state_attr) -> None:
        """Initialize the binary sensor."""
        super().__init__(broker, device)

        self._state_attr = state_attr

        if device.type[:21] == "Dual Channel Receiver":
            self._attr_name = f"{device.type[:21]} {device.id}"
        else:
            self._attr_name = f"{device.type} {device.id}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"][self._state_attr]
