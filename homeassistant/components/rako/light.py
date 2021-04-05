"""Platform for light integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import python_rako
from python_rako.exceptions import RakoBridgeError
from python_rako.helpers import convert_to_brightness, convert_to_scene

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

from . import DATA_RAKO_BRIDGE_CLIENT, DOMAIN
from .const import ATTR_CHANNEL_ID, ATTR_MANUFACTURER, ATTR_ROOM_ID
from .util import create_unique_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the config entry."""
    bridge = hass.data[DOMAIN][entry.entry_id][DATA_RAKO_BRIDGE_CLIENT]

    hass_lights: list[Entity] = []
    session = async_get_clientsession(hass)

    bridge.level_cache, bridge.scene_cache = await bridge.get_cache_state()

    async for light in bridge.discover_lights(session):
        if isinstance(light, python_rako.ChannelLight):
            hass_light: RakoLight = RakoChannelLight(bridge, light)
        elif isinstance(light, python_rako.RoomLight):
            hass_light = RakoRoomLight(bridge, light)
        else:
            continue

        hass_lights.append(hass_light)

    async_add_entities(hass_lights, True)


class RakoLight(LightEntity):
    """Representation of a Rako Light."""

    def __init__(self, bridge, light: python_rako.Light):
        """Initialize a RakoLight."""
        self.bridge = bridge
        self._light = light
        self._brightness = self._init_get_brightness_from_cache()
        self._available = True

    def _init_get_brightness_from_cache(self) -> int:
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await self.bridge.register_for_state_updates(self)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await self.bridge.deregister_for_state_updates(self)

    @property
    def unique_id(self) -> str | None:
        """Light's unique ID."""
        return create_unique_id(
            self.bridge.entry_id, self._light.room_id, self._light.channel_id
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        """Set the brightness. Used when state is updated outside Home Assistant."""
        self._brightness = value
        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.brightness > 0

    @property
    def should_poll(self) -> bool:
        """Entity pushes its state to HA."""
        return False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.async_turn_on(brightness=0)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this Rako Light."""
        return {
            ATTR_MANUFACTURER: "Rako",
            ATTR_ROOM_ID: self._light.room_id,
            ATTR_CHANNEL_ID: self._light.channel_id,
        }


class RakoRoomLight(RakoLight):
    """Representation of a Rako Room Light."""

    def __init__(self, bridge, light: python_rako.RoomLight):
        """Initialize a RakoLight."""
        super().__init__(bridge, light)
        self._light = light

    def _init_get_brightness_from_cache(self) -> int:
        scene_of_room = self.bridge.scene_cache.get(self._light.room_id, 0)
        brightness = convert_to_brightness(scene_of_room)
        return brightness

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._light.room_title

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        try:
            scene = convert_to_scene(brightness)
            await asyncio.wait_for(
                self.bridge.set_room_scene(self._light.room_id, scene), timeout=3.0
            )

        except (RakoBridgeError, asyncio.TimeoutError):
            if self._available:
                _LOGGER.error("An error occurred while updating the Rako Light")
            self._available = False
            return


class RakoChannelLight(RakoLight):
    """Representation of a Rako Channel Light."""

    def __init__(self, bridge, light: python_rako.ChannelLight):
        """Initialize a RakoLight."""
        super().__init__(bridge, light)
        self._light = light

    def _init_get_brightness_from_cache(self) -> int:
        scene_of_room = self.bridge.scene_cache.get(self._light.room_id, 0)
        brightness = self.bridge.level_cache.get_channel_level(
            self._light.room_channel, scene_of_room
        )
        return brightness

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return f"{self._light.room_title} - {self._light.channel_name}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        try:
            await asyncio.wait_for(
                self.bridge.set_channel_brightness(
                    self._light.room_id, self._light.channel_id, brightness
                ),
                timeout=3.0,
            )

        except (RakoBridgeError, asyncio.TimeoutError):
            if self._available:
                _LOGGER.error("An error occurred while updating the Rako Light")
            self._available = False
            return
