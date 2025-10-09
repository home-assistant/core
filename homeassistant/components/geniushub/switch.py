"""Support for Genius Hub switch/outlet devices."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import ATTR_DURATION, GeniusHubConfigEntry
from .entity import GeniusZone

GH_ON_OFF_ZONE = "on / off"

SVC_SET_SWITCH_OVERRIDE = "set_switch_override"

SET_SWITCH_OVERRIDE_SCHEMA: VolDictType = {
    vol.Optional(ATTR_DURATION): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Genius Hub switch entities."""

    broker = entry.runtime_data

    async_add_entities(
        GeniusSwitch(broker, z)
        for z in broker.client.zone_objs
        if z.data.get("type") == GH_ON_OFF_ZONE
    )

    # Register custom services
    platform = entity_platform.async_get_current_platform()

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
        return SwitchDeviceClass.OUTLET

    @property
    def is_on(self) -> bool:
        """Return the current state of the on/off zone.

        The zone is considered 'on' if the mode is either 'override' or 'timer'.
        """
        return (
            self._zone.data["mode"] in ["override", "timer"]
            and self._zone.data["setpoint"]
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the zone to Timer mode.

        The zone is deemed 'off' in this mode, although the plugs may actually be on.
        """
        await self._zone.set_mode("timer")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the zone to override/on ({'setpoint': true}) for x seconds."""
        await self._zone.set_override(1, kwargs.get(ATTR_DURATION, 3600))
