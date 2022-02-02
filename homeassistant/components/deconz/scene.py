"""Support for deCONZ scenes."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

from pydeconz.group import Scene as PydeconzScene

from homeassistant.components.scene import DOMAIN, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as DECONZ_DOMAIN
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry


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
        entities = [
            DeconzScene(scene, gateway)
            for scene in scenes
            if scene.deconz_id not in gateway.entities[DOMAIN]
        ]

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


class DeconzScene(DeconzDevice, Scene):
    """Representation of a deCONZ scene."""

    TYPE = DOMAIN

    _device: PydeconzScene

    def __init__(self, device: PydeconzScene, gateway: DeconzGateway) -> None:
        """Set up a scene."""
        self._unique_id = f"{gateway.bridgeid}-{device.deconz_id}"
        super().__init__(device, gateway)

        self._attr_name = device.full_name
        self._group_identifier = f"{gateway.bridgeid}-{device.group_deconz_id}"

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.recall()

    @property
    def available(self):
        """Return True if device is available."""
        return self.gateway.available

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this scene."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(identifiers={(DECONZ_DOMAIN, self._group_identifier)})
