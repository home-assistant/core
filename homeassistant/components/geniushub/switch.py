"""Support for Genius Hub switch/outlet devices."""
from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, GeniusZone

GH_ZONE_ATTR = "on / off"


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
        if GH_ZONE_ATTR in z.data["type"]
    ]

    async_add_entities(switches, update_before_add=True)


class GeniusSwitch(GeniusZone, SwitchDevice):
    """Representation of a Genius Hub switch."""

    def __init__(self, broker, zone) -> None:
        """Initialize the switch."""
        super().__init__(broker, zone)

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        # off, override, timer, footprint
        # technially this could be untrue, if we're using the timer
        return self._zone.data["mode"] != "off"

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._zone.set_mode("off")
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # geniusclient doesn't (yet) have a way to specify the override for this
        await self._zone.set_mode("override")
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()
