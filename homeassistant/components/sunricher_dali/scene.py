"""Support for DALI Center Scene entities."""

import logging
from typing import Any

from PySrDaliGateway import CallbackEventType, Scene
from PySrDaliGateway.helper import gen_device_unique_id, gen_group_unique_id

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DALI Center scene entities from config entry."""
    scenes = entry.runtime_data.scenes

    scene_entities: list[DaliCenterScene] = []
    for scene in scenes:
        try:
            scene_details = await scene.read_scene()
            scene_entities.append(DaliCenterScene(scene, scene_details))
        except (OSError, ValueError, KeyError):
            _LOGGER.exception(
                "Failed to read scene details for %s, skipping scene",
                scene.name,
            )

    if scene_entities:
        async_add_entities(scene_entities)


class DaliCenterScene(SceneEntity):
    """Representation of a DALI Center Scene."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, scene: Scene, scene_details: dict[str, Any]) -> None:
        """Initialize the DALI scene."""

        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = scene.unique_id
        self._scene_details = scene_details
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, scene.gw_sn)},
        )
        self._attr_extra_state_attributes = {
            "gateway_sn": scene.gw_sn,
            "scene_id": scene.scene_id,
            "area_id": scene_details["area_id"],
            "channel": scene_details["channel"],
            "entity_id": [],
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        self.async_on_remove(
            self._scene.register_listener(
                CallbackEventType.ONLINE_STATUS, self._handle_availability
            )
        )

        self._update_entity_mappings()

    @callback
    def _handle_availability(self, available: bool) -> None:
        """Handle gateway availability changes."""
        self._attr_available = available
        self.schedule_update_ha_state()

    def _update_entity_mappings(self) -> None:
        """Update entity ID mappings in extra_state_attributes."""
        ent_reg = er.async_get(self.hass)
        mapped_entities: list[str] = []

        for device in self._scene_details["devices"]:
            if device["dev_type"] == "0401":
                device_unique_id = gen_group_unique_id(
                    device["address"],
                    device["channel"],
                    self._scene.gw_sn,
                )
            else:
                device_unique_id = gen_device_unique_id(
                    device["dev_type"],
                    device["channel"],
                    device["address"],
                    self._scene.gw_sn,
                )
            entity_id = ent_reg.async_get_entity_id("light", DOMAIN, device_unique_id)

            if entity_id:
                mapped_entities.append(entity_id)

        self._attr_extra_state_attributes["entity_id"] = mapped_entities

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the DALI scene."""
        _LOGGER.debug("Activating scene: %s", self._attr_name)
        await self.hass.async_add_executor_job(self._scene.activate)
