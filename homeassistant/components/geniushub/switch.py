"""Support for Genius Hub switch/outlet devices."""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.switch import DEVICE_CLASS_OUTLET, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.typing import ConfigType

from . import ATTR_DURATION, DOMAIN, GeniusZone

GH_ON_OFF_ZONE = "on / off"

SVC_SET_SWITCH_OVERRIDE = "set_switch_override"

SET_SWITCH_OVERRIDE_SCHEMA = {
    vol.Optional(ATTR_DURATION): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
    ),
}


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
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

    # Register custom services
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SVC_SET_SWITCH_OVERRIDE,
        SET_SWITCH_OVERRIDE_SCHEMA,
        "async_turn_on",
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
