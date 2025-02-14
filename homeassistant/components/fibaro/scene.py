"""Support for Fibaro scenes."""

from __future__ import annotations

from typing import Any

from pyfibaro.fibaro_scene import SceneModel

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import FibaroConfigEntry, FibaroController
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FibaroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro scenes."""
    controller = entry.runtime_data
    async_add_entities(
        [FibaroScene(scene, controller) for scene in controller.read_scenes()],
        True,
    )


class FibaroScene(Scene):
    """Representation of a Fibaro scene entity."""

    def __init__(self, fibaro_scene: SceneModel, controller: FibaroController) -> None:
        """Initialize the Fibaro scene."""
        self._fibaro_scene = fibaro_scene

        room_name = controller.get_room_name(fibaro_scene.room_id)
        if not room_name:
            room_name = "Unknown"

        self._attr_name = f"{room_name} {fibaro_scene.name}"
        self._attr_unique_id = (
            f"{slugify(controller.hub_serial)}.scene.{fibaro_scene.fibaro_id}"
        )
        self._attr_extra_state_attributes = {"fibaro_id": fibaro_scene.fibaro_id}
        # propagate hidden attribute set in fibaro home center to HA
        self._attr_entity_registry_visible_default = fibaro_scene.visible
        # All scenes are shown on hub device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.hub_serial)}
        )

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._fibaro_scene.start()
