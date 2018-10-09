"""
Support for control of ElkM1 tasks ("macros").

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.elkm1/
"""


from homeassistant.components.elkm1 import (
    DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities)
from homeassistant.components.scene import Scene

DEPENDENCIES = [ELK_DOMAIN]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Create the Elk-M1 switch platform."""
    if discovery_info is None:
        return
    elk = hass.data[ELK_DOMAIN]['elk']
    entities = create_elk_entities(hass, elk.tasks, 'task', ElkTask, [])
    async_add_entities(entities, True)


class ElkTask(ElkEntity, Scene):
    """Elk-M1 task as scene."""

    def __init__(self, element, elk, elk_data):
        """Initialize output."""
        super().__init__(element, elk, elk_data)

    async def async_activate(self, **kwargs):
        """Activate the task."""
        self._element.activate()
