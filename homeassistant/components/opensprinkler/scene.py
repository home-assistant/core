"""Opensprinkler integration."""
import logging
from typing import Any, Callable

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: dict, async_add_entities: Callable,
):
    """Set up the opensprinkler scenes."""
    entities = _create_entities(hass, config)
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict):
    entities = []

    device = hass.data[DOMAIN][config.entry_id]
    for program in device.programs:
        entities.append(ProgramScene(config.entry_id, program, device))

    return entities


class ProgramScene(Scene):
    """Represent a scene for a program."""

    def __init__(self, entry_id, program, device):
        """Set up a new opensprinkler scene."""
        self._entry_id = entry_id
        self._program = program
        self._device = device
        self._entity_type = "scene"

    @property
    def name(self) -> str:
        """Return the name of this scene."""
        return self._program.name

    @property
    def should_poll(self) -> bool:
        """Return that polling is not necessary."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_program_{self._program.name}"

    async def async_activate(self, **kwargs: Any) -> None:
        """Run the program."""
        await self.hass.async_add_executor_job(self._program.run)
