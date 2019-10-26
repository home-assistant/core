"""Support for Genius Hub switch/outlet devices."""
from homeassistant.components.switch import SwitchDevice, DEVICE_CLASS_OUTLET
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, GeniusZone

GH_ON_OFF_ZONE = "on / off"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the Genius Hub switch entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    switches = [
        GeniusSwitch(broker, z)
        for z in broker.client.zone_objs
        if z.data["type"] == GH_ON_OFF_ZONE
    ]

    async_add_entities(switches)


class GeniusSwitch(GeniusZone, SwitchDevice):
    """Representation of a Genius Hub switch."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        # off, override, timer, footprint
        # technially this could be untrue, if we're using the timer
        return self._zone.data["mode"] != "off"

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._zone.set_mode("off")

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # geniusclient doesn't (yet) have a way to specify the override for this
        await self._zone.set_mode("override")
