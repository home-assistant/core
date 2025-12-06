"""Support for DALI Center Scene entities."""

import logging
from typing import Any

from propcache.api import cached_property
from PySrDaliGateway import Scene

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import DaliCenterEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DALI Center scene entities from config entry."""
    async_add_entities(DaliCenterScene(scene) for scene in entry.runtime_data.scenes)


class DaliCenterScene(DaliCenterEntity, SceneEntity):
    """Representation of a DALI Center Scene."""

    def __init__(self, scene: Scene) -> None:
        """Initialize the DALI scene."""
        super().__init__(scene)
        self._scene = scene
        self._attr_name = scene.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, scene.gw_sn)},
        )

    @cached_property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """Return the scene state attributes."""
        ent_reg = er.async_get(self.hass)
        return {
            "entity_id": [
                entity_id
                for device in self._scene.devices
                if (
                    entity_id := ent_reg.async_get_entity_id(
                        "light", DOMAIN, device["unique_id"]
                    )
                )
            ]
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the DALI scene."""
        _LOGGER.debug("Activating scene: %s", self._attr_name)
        await self.hass.async_add_executor_job(self._scene.activate)
