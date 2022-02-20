"""Support for Axis switches."""
from axis.event_stream import CLASS_OUTPUT

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .axis_base import AxisEventBase
from .const import DOMAIN as AXIS_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Axis switch."""
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    @callback
    def async_add_switch(event_id):
        """Add switch from Axis device."""
        event = device.api.event[event_id]

        if event.CLASS == CLASS_OUTPUT:
            async_add_entities([AxisSwitch(event, device)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, device.signal_new_event, async_add_switch)
    )


class AxisSwitch(AxisEventBase, SwitchEntity):
    """Representation of a Axis switch."""

    def __init__(self, event, device):
        """Initialize the Axis switch."""
        super().__init__(event, device)

        if event.id and device.api.vapix.ports[event.id].name:
            self._attr_name = f"{device.name} {device.api.vapix.ports[event.id].name}"

    @property
    def is_on(self):
        """Return true if event is active."""
        return self.event.is_tripped

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        await self.device.api.vapix.ports[self.event.id].close()

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        await self.device.api.vapix.ports[self.event.id].open()
