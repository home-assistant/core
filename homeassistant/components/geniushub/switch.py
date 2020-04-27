"""Support for Genius Hub switch/outlet devices."""
from homeassistant.components.switch import DEVICE_CLASS_OUTLET, SwitchEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, GeniusZone

ATTR_DURATION = "duration"

GH_ON_OFF_ZONE = "on / off"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
) -> None:
    """Set up the Genius Hub switch entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    async_add_entities(
        [
            GeniusSwitch(broker, z)
            for z in broker.client.zone_objs
            if z.data["type"] == GH_ON_OFF_ZONE
        ]
    )


class GeniusSwitch(GeniusZone, SwitchEntity):
    """Representation of a Genius Hub switch."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    @property
    def is_on(self) -> bool:
        """Return the current state of the on/off zone.

        The zone is considered 'on' if & only if it is override/on (e.g. timer/on is 'off').
        """
        return self._zone.data["mode"] == "override" and self._zone.data["setpoint"]

    async def async_turn_off(self, **kwargs) -> None:
        """Send the zone to Timer mode.

        The zone is deemed 'off' in this mode, although the plugs may actually be on.
        """
        await self._zone.set_mode("timer")

    async def async_turn_on(self, **kwargs) -> None:
        """Set the zone to override/on ({'setpoint': true}) for x seconds."""
        await self._zone.set_override(1, kwargs.get(ATTR_DURATION, 3600))
