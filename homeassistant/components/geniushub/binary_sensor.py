"""Support for Genius Hub binary_sensor devices."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, GeniusDevice

GH_STATE_ATTR = "outputOnOff"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    switches = [
        GeniusBinarySensor(broker, d, GH_STATE_ATTR)
        for d in broker.client.device_objs
        if GH_STATE_ATTR in d.data["state"]
    ]

    async_add_entities(switches, update_before_add=True)


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
