"""Support for control of ElkM1 tasks ("macros")."""
from homeassistant.components.scene import Scene

from . import ElkAttachedEntity, create_elk_entities
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the Elk-M1 scene platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    elk = elk_data["elk"]
    create_elk_entities(elk_data, elk.tasks, "task", ElkTask, entities)
    async_add_entities(entities, True)


class ElkTask(ElkAttachedEntity, Scene):
    """Elk-M1 task as scene."""

    async def async_activate(self):
        """Activate the task."""
        self._element.activate()
