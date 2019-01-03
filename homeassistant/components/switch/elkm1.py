"""
Support for control of ElkM1 outputs (relays).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.elkm1/
"""


from homeassistant.components.elkm1 import (
    DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities)
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = [ELK_DOMAIN]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Create the Elk-M1 switch platform."""
    if discovery_info is None:
        return
    elk = hass.data[ELK_DOMAIN]['elk']
    entities = create_elk_entities(hass, elk.outputs, 'output', ElkOutput, [])
    async_add_entities(entities, True)


class ElkOutput(ElkEntity, SwitchDevice):
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
