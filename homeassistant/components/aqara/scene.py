"""Support for Aqara scenes."""
from __future__ import annotations

from typing import Any

from aqara_iot import AqaraHomeManager, AqaraScene

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara scenes."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]
    scenes = await hass.async_add_executor_job(hass_data.home_manager.query_scenes)
    async_add_entities(
        AqaraSceneEntity(hass_data.home_manager, scene) for scene in scenes
    )


class AqaraSceneEntity(Scene):
    """Aqara Scene Remote."""

    _should_poll = False

    def __init__(self, home_manager: AqaraHomeManager, scene: AqaraScene) -> None:
        """Init Aqara Scene."""
        super().__init__()
        self._attr_unique_id = f"{scene.scene_id}"
        self.home_manager = home_manager
        self.scene = scene

    @property
    def name(self) -> str | None:
        """Return Aqara scene name."""
        return self.scene.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.unique_id}")},
            manufacturer="aqara",
            name=self.scene.name,
            model="Aqara Scene",
        )

    @property
    def available(self) -> bool:
        """Return if the scene is enabled."""
        return self.scene.enabled

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.home_manager.trigger_scene(self.scene.position_id, self.scene.scene_id)
