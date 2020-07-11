"""Support for Vera scenes."""
import logging
from typing import Any, Callable, List

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN, VERA_ID_FORMAT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    controller_data = hass.data[DOMAIN]
    async_add_entities(
        [
            VeraScene(device, controller_data.controller)
            for device in controller_data.scenes
        ]
    )


class VeraScene(Scene):
    """Representation of a Vera scene entity."""

    def __init__(self, vera_scene, controller):
        """Initialize the scene."""
        self.vera_scene = vera_scene
        self.controller = controller

        self._name = self.vera_scene.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_scene.name), vera_scene.scene_id
        )

    def update(self):
        """Update the scene status."""
        self.vera_scene.refresh()

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.vera_scene.activate()

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the scene."""
        return {"vera_scene_id": self.vera_scene.vera_scene_id}
