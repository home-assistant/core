"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant

from .const import DATA_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable,
    discovery_info: dict,
):
    """Set up the opensprinkler scenes."""
    entities = await hass.async_add_executor_job(
        _create_entities, hass, config, discovery_info
    )
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict, discovery_info: dict):
    entities = []

    name = discovery_info["name"]
    device = hass.data[DOMAIN][DATA_DEVICES][name]

    for program in device.getPrograms():
        entities.append(ProgramScene(program, device))

    return entities


class ProgramScene(Scene):
    """Represent a scene for a program."""

    def __init__(self, program, device):
        """Set up a new opensprinkler scene."""
        self._program = program
        self._device = device

    @property
    def name(self) -> str:
        """Return the name of this scene."""
        return self._program.name

    @property
    def should_poll(self) -> bool:
        """Return that polling is not necessary."""
        return False

    async def async_activate(self) -> None:
        """Run the program."""
        self._program.run()
