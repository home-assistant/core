"""Support for Genius Hub switch/outlet devices."""
from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import DOMAIN, DEVICE_CLASS_OUTLET, GeniusEntity

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


class GeniusSwitch(GeniusEntity, SwitchDevice):
    """Representation of a Genius Hub switch."""

    def __init__(self, broker, zone) -> None:
        """Initialize the Zone."""
        super().__init__()

        self._zone = zone
        self._unique_id = f"{broker.hub_uid}_zone_{zone.id}"

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        status = {k: v for k, v in self._zone.data.items() if k in GH_ZONE_ATTRS}
        return {"status": status}

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
