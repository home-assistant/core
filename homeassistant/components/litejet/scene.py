"""Support for LiteJet scenes."""
import logging
from typing import Any

from homeassistant.components.scene import Scene

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""

    system = hass.data[DOMAIN]

    def get_entities(system):
        entities = []
        for i in system.scenes():
            name = system.get_scene_name(i)
            entities.append(LiteJetScene(config_entry.entry_id, system, i, name))
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities, system), True)


class LiteJetScene(Scene):
    """Representation of a single LiteJet scene."""

    def __init__(self, entry_id, lj, i, name):
        """Initialize the scene."""
        self._entry_id = entry_id
        self._lj = lj
        self._index = i
        self._name = name

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this scene."""
        return f"{self._entry_id}_{self._index}"

    @property
    def extra_state_attributes(self):
        """Return the device-specific state attributes."""
        return {ATTR_NUMBER: self._index}

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lj.activate_scene(self._index)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Scenes are only enabled by explicit user choice."""
        return False
