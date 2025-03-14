"""Support for Tuya scenes."""

from __future__ import annotations

from typing import Any

from tuya_sharing import Manager, SharingScene

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya scenes."""
    hass_data = entry.runtime_data
    scenes = await hass.async_add_executor_job(hass_data.manager.query_scenes)
    async_add_entities(TuyaSceneEntity(hass_data.manager, scene) for scene in scenes)


class TuyaSceneEntity(Scene):
    """Tuya Scene Remote."""

    _should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, home_manager: Manager, scene: SharingScene) -> None:
        """Init Tuya Scene."""
        super().__init__()
        self._attr_unique_id = f"tys{scene.scene_id}"
        self.home_manager = home_manager
        self.scene = scene

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.unique_id}")},
            manufacturer="tuya",
            name=self.scene.name,
            model="Tuya Scene",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return if the scene is enabled."""
        return self.scene.enabled

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.home_manager.trigger_scene(self.scene.home_id, self.scene.scene_id)
