"""Support for Powerview scenes from a Powerview hub."""
from typing import Any

from aiopvapi.resources.scene import Scene as PvScene
import voluptuous as vol

from homeassistant.components.scene import Scene
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PLATFORM
import homeassistant.helpers.config_validation as cv

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DOMAIN,
    HUB_ADDRESS,
    PV_API,
    PV_ROOM_DATA,
    PV_SCENE_DATA,
    ROOM_NAME_UNICODE,
    STATE_ATTRIBUTE_ROOM_NAME,
)
from .entity import HDEntity

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): DOMAIN, vol.Required(HUB_ADDRESS): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import platform from yaml."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: config[HUB_ADDRESS]},
        )
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up powerview scene entries."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    scene_data = pv_data[PV_SCENE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    pvscenes = (
        PowerViewScene(
            PvScene(raw_scene, pv_request), room_data, coordinator, device_info
        )
        for scene_id, raw_scene in scene_data.items()
    )
    async_add_entities(pvscenes)


class PowerViewScene(HDEntity, Scene):
    """Representation of a Powerview scene."""

    def __init__(self, scene, room_data, coordinator, device_info):
        """Initialize the scene."""
        super().__init__(coordinator, device_info, scene.id)
        self._scene = scene
        self._room_name = room_data.get(scene.room_id, {}).get(ROOM_NAME_UNICODE, "")

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {STATE_ATTRIBUTE_ROOM_NAME: self._room_name}

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:blinds"

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        await self._scene.activate()
