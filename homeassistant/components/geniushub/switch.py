"""Support for Genius Hub switch/outlet devices."""

from datetime import timedelta
from typing import Any, override

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GeniusHubConfigEntry
from .const import ATTR_DURATION
from .entity import GeniusZone

GH_ON_OFF_ZONE = "on / off"


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


class GeniusSwitch(GeniusZone, SwitchEntity):
    """Representation of a Genius Hub switch."""

    @property
    @override
    def device_class(self) -> SwitchDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SwitchDeviceClass.OUTLET

    @property
    @override
    def is_on(self) -> bool:
        """Return the current state of the on/off zone.

        The zone is considered 'on' if the mode is either 'override' or 'timer'.
        """
        return (
            self._zone.data["mode"] in ["override", "timer"]
            and self._zone.data["setpoint"]
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the zone to Timer mode.

        The zone is deemed 'off' in this mode, although the plugs may actually be on.
        """
        await self._zone.set_mode("timer")

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the zone to override/on ({'setpoint': true}) for x seconds."""
        duration: timedelta = kwargs.get(ATTR_DURATION, timedelta(hours=1))
        await self._zone.set_override(1, int(duration.total_seconds()))
