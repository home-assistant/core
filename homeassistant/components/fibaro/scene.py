"""Support for Fibaro scenes."""
from __future__ import annotations

from typing import Any

from pyfibaro.fibaro_scene import SceneModel

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro scenes."""
    async_add_entities(
        [
            FibaroScene(scene)
            for scene in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.SCENE
            ]
        ],
        True,
    )


class FibaroScene(FibaroDevice, Scene):
    """Representation of a Fibaro scene entity."""

    def __init__(self, fibaro_device: SceneModel) -> None:
        """Initialize the Fibaro scene."""
        super().__init__(fibaro_device)

        # All scenes are shown on hub device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.controller.hub_serial)}
        )

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.fibaro_device.start()
