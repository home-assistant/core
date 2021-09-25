"""Support for Tuya scenes."""
from __future__ import annotations

import logging
from typing import Any

from tuya_iot import TuyaHomeManager, TuyaScene

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TUYA_HOME_MANAGER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya scenes."""
    entities = []

    home_manager = hass.data[DOMAIN][entry.entry_id][TUYA_HOME_MANAGER]
    scenes = await hass.async_add_executor_job(home_manager.query_scenes)
    for scene in scenes:
        entities.append(TuyaHAScene(home_manager, scene))

    async_add_entities(entities)


class TuyaHAScene(Scene):
    """Tuya Scene Remote."""

    def __init__(self, home_manager: TuyaHomeManager, scene: TuyaScene) -> None:
        """Init Tuya Scene."""
        super().__init__()
        self.home_manager = home_manager
        self.scene = scene

    @property
    def should_poll(self) -> bool:
        """Hass should not poll."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"tys{self.scene.scene_id}"

    @property
    def name(self) -> str | None:
        """Return Tuya scene name."""
        return self.scene.name

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, f"{self.unique_id}")},
            "manufacturer": "tuya",
            "name": self.scene.name,
            "model": "Tuya Scene",
        }

    @property
    def available(self) -> bool:
        """Return if the scene is enabled."""
        return self.scene.enabled

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.home_manager.trigger_scene(self.scene.home_id, self.scene.scene_id)
