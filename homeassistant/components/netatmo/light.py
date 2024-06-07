"""Support for the Netatmo camera lights."""

from __future__ import annotations

import logging
from typing import Any

from pyatmo import modules as NaModules

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_CONTROL,
    CONF_URL_SECURITY,
    DOMAIN,
    EVENT_TYPE_LIGHT_MODE,
    NETATMO_CREATE_CAMERA_LIGHT,
    NETATMO_CREATE_LIGHT,
    WEBHOOK_LIGHT_MODE,
    WEBHOOK_PUSH_TYPE,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo camera light platform."""

    @callback
    def _create_camera_light_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "floodlight"):
            return

        entity = NetatmoCameraLight(netatmo_device)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_CAMERA_LIGHT, _create_camera_light_entity
        )
    )

    @callback
    def _create_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "brightness"):
            return

        entity = NetatmoLight(netatmo_device)
        _LOGGER.debug("Adding light %s", entity)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_LIGHT, _create_entity)
    )


class NetatmoCameraLight(NetatmoModuleEntity, LightEntity):
    """Representation of a Netatmo Presence camera light."""

    device: NaModules.NOC
    _attr_is_on = False
    _attr_name = None
    _attr_configuration_url = CONF_URL_SECURITY
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize a Netatmo Presence camera light."""
        super().__init__(netatmo_device)
        self._attr_unique_id = f"{self.device.entity_id}-light"

        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.async_on_remove(
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
            data["home_id"] == self.home.entity_id
            and data["camera_id"] == self.device.entity_id
            and data[WEBHOOK_PUSH_TYPE] == WEBHOOK_LIGHT_MODE
        ):
            self._attr_is_on = bool(data["sub_type"] == "on")

            self.async_write_ha_state()
            return

    @property
    def available(self) -> bool:
        """If the webhook is not established, mark as unavailable."""
        return bool(self.data_handler.webhook)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self.name)
        await self.device.async_floodlight_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' to auto mode", self.name)
        await self.device.async_floodlight_auto()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = bool(self.device.floodlight == "on")


class NetatmoLight(NetatmoModuleEntity, LightEntity):
    """Representation of a dimmable light by Legrand/BTicino."""

    _attr_name = None
    _attr_configuration_url = CONF_URL_CONTROL
    _attr_brightness: int | None = 0
    device: NaModules.NLFN

    def __init__(self, netatmo_device: NetatmoDevice) -> None:
        """Initialize a Netatmo light."""
        super().__init__(netatmo_device)
        self._attr_unique_id = f"{self.device.entity_id}-light"

        if self.device.brightness is not None:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}

        self._signal_name = f"{HOME}-{self.home.entity_id}"
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self.device.async_set_brightness(kwargs[ATTR_BRIGHTNESS])

        else:
            await self.device.async_on()

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.device.async_off()
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.on is True

        if (brightness := self.device.brightness) is not None:
            # Netatmo uses a range of [0, 100] to control brightness
            self._attr_brightness = round((brightness / 100) * 255)
        else:
            self._attr_brightness = None
