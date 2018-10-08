"""
Support for control of ElkM1 outputs (relays) and tasks ("macros).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.elkm1/
"""

from homeassistant.helpers.entity import ToggleEntity

from homeassistant.components.elkm1 import (
    DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities)

DEPENDENCIES = [ELK_DOMAIN]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setup the Elk switch platform."""
    if discovery_info is None:
        return
    elk = hass.data[ELK_DOMAIN]['elk']
    entities = create_elk_entities(hass, elk.tasks, 'task', ElkTask, [])
    entities = create_elk_entities(
        hass, elk.outputs, 'output', ElkOutput, entities)
    async_add_entities(entities, True)


class ElkOutput(ElkEntity, ToggleEntity):
    """Elk Output as Toggle Switch."""

    def __init__(self, element, elk, elk_data):
        """Initialize output."""
        super().__init__('switch', element, elk, elk_data)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:toggle-switch'

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


class ElkTask(ElkEntity, ToggleEntity):
    """Elk Output as Toggle Switch."""

    def __init__(self, element, elk, elk_data):
        """Initialize output."""
        super().__init__('switch', element, elk, elk_data)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:toggle-switch'

    @property
    def device_state_attributes(self):
        """Attributes of the task."""
        attrs = self.initial_attrs()
        attrs['last_change'] = self._element.last_change
        return attrs

    @property
    def is_on(self) -> bool:
        """Get the task status."""
        return False

    async def async_turn_on(self, **kwargs):
        """Activate the task."""
        self._element.activate()

    async def async_turn_off(self, **kwargs):
        """Turn off the task.

        Tasks aren't actually never turned "on", they are just
        triggered, so their state is always off.
        """
        pass
