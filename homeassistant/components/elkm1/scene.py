"""Support for control of ElkM1 tasks ("macros")."""
from homeassistant.components.scene import Scene

from . import DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the Elk-M1 scene platform."""
    if discovery_info is None:
        return
    elk_datas = hass.data[ELK_DOMAIN]
    entities = []
    for elk_data in elk_datas.values():
        elk = elk_data["elk"]
        entities = create_elk_entities(elk_data, elk.tasks, "task", ElkTask, entities)
    async_add_entities(entities, True)


class ElkTask(ElkEntity, Scene):
    """Elk-M1 task as scene."""

    async def async_activate(self):
        """Activate the task."""
        self._element.activate()
