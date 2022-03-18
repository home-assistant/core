"""Support for deCONZ scenes."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

from pydeconz.group import Scene as PydeconzScene

from homeassistant.components.scene import DOMAIN, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzSceneMixin
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scenes for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_scene(
        scenes: list[PydeconzScene]
        | ValuesView[PydeconzScene] = gateway.api.scenes.values(),
    ) -> None:
        """Add scene from deCONZ."""
        entities = []

        for scene in scenes:

            known_entities = set(gateway.entities[DOMAIN])
            new_entity = DeconzScene(scene, gateway)
            if new_entity.unique_id not in known_entities:
                entities.append(new_entity)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_scene,
            async_add_scene,
        )
    )

    async_add_scene()


class DeconzScene(DeconzSceneMixin, Scene):
    """Representation of a deCONZ scene."""

    TYPE = DOMAIN

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.recall()
