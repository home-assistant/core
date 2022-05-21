"""Support for the Netatmo camera lights."""
from __future__ import annotations

import logging
from typing import Any, cast

import pyatmo

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_HANDLER,
    DOMAIN,
    EVENT_TYPE_LIGHT_MODE,
    MANUFACTURER,
    SIGNAL_NAME,
    TYPE_SECURITY,
    WEBHOOK_LIGHT_MODE,
    WEBHOOK_PUSH_TYPE,
)
from .data_handler import CAMERA_DATA_CLASS_NAME, NetatmoDataHandler
from .netatmo_entity_base import NetatmoBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo camera light platform."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]
    data_class = data_handler.data.get(CAMERA_DATA_CLASS_NAME)

    if not data_class or data_class.raw_data == {}:
        raise PlatformNotReady

    all_cameras = []
    for home in data_handler.data[CAMERA_DATA_CLASS_NAME].cameras.values():
        for camera in home.values():
            all_cameras.append(camera)

    entities = [
        NetatmoLight(
            data_handler,
            camera["id"],
            camera["type"],
            camera["home_id"],
        )
        for camera in all_cameras
        if camera["type"] == "NOC"
    ]

    _LOGGER.debug("Adding camera lights %s", entities)
    async_add_entities(entities, True)


class NetatmoLight(NetatmoBase, LightEntity):
    """Representation of a Netatmo Presence camera light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        camera_id: str,
        camera_type: str,
        home_id: str,
    ) -> None:
        """Initialize a Netatmo Presence camera light."""
        LightEntity.__init__(self)
        super().__init__(data_handler)

        self._data_classes.append(
            {"name": CAMERA_DATA_CLASS_NAME, SIGNAL_NAME: CAMERA_DATA_CLASS_NAME}
        )
        self._id = camera_id
        self._home_id = home_id
        self._model = camera_type
        self._netatmo_type = TYPE_SECURITY
        self._device_name: str = self._data.get_camera(camera_id)["name"]
        self._attr_name = f"{MANUFACTURER} {self._device_name}"
        self._is_on = False
        self._attr_unique_id = f"{self._id}-light"

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.data_handler.config_entry.async_on_unload(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-{EVENT_TYPE_LIGHT_MODE}",
                self.handle_event,
            )
        )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if not data.get("camera_id"):
            return

        if (
            data["home_id"] == self._home_id
            and data["camera_id"] == self._id
            and data[WEBHOOK_PUSH_TYPE] == WEBHOOK_LIGHT_MODE
        ):
            self._is_on = bool(data["sub_type"] == "on")

            self.async_write_ha_state()
            return

    @property
    def _data(self) -> pyatmo.AsyncCameraData:
        """Return data for this entity."""
        return cast(
            pyatmo.AsyncCameraData,
            self.data_handler.data[self._data_classes[0]["name"]],
        )

    @property
    def available(self) -> bool:
        """If the webhook is not established, mark as unavailable."""
        return bool(self.data_handler.webhook)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self.name)
        await self._data.async_set_state(
            home_id=self._home_id,
            camera_id=self._id,
            floodlight="on",
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' to auto mode", self.name)
        await self._data.async_set_state(
            home_id=self._home_id,
            camera_id=self._id,
            floodlight="auto",
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._is_on = bool(self._data.get_light_state(self._id) == "on")
