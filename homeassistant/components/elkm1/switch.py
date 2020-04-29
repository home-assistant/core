"""Support for control of ElkM1 outputs (relays)."""
from homeassistant.components.switch import SwitchDevice

from . import ElkAttachedEntity, create_elk_entities
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the Elk-M1 switch platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    elk = elk_data["elk"]
    create_elk_entities(elk_data, elk.outputs, "output", ElkOutput, entities)
    async_add_entities(entities, True)


class ElkOutput(ElkAttachedEntity, SwitchDevice):
    """Elk output as switch."""

    @property
    def is_on(self) -> bool:
        """Get the current output status."""
        return self._element.output_on

    async def async_turn_on(self, **kwargs):
        """Turn on the output."""
        self._element.turn_on(0)

    async def async_turn_off(self, **kwargs):
        """Turn off the output."""
        self._element.turn_off()
