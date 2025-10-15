"""Support for the Netatmo camera lights."""

from __future__ import annotations

import logging
from typing import Any

from pyatmo import modules as NaModules

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_EVENT_TYPE,
    CONF_URL_CONTROL,
    CONF_URL_SECURITY,
    DOMAIN,
    EVENT_TYPE_LIGHT_MODE,
    NETATMO_CREATE_CAMERA_LIGHT,
    NETATMO_CREATE_LIGHT,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo camera light platform."""

    @callback
    def _create_camera_light_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "floodlight"):
            return

        entity = NetatmoCameraLight(netatmo_device)
        _LOGGER.debug("Adding camera light %s", netatmo_device.device.name)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_CAMERA_LIGHT, _create_camera_light_entity
        )
    )

    @callback
    def _create_light_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "brightness"):
            return

        entity = NetatmoLight(netatmo_device)
        _LOGGER.debug("Adding regular light %s", netatmo_device.device.name)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_LIGHT, _create_light_entity)
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
        event_type = data.get(ATTR_EVENT_TYPE)

        if not event_type:
            _LOGGER.debug("Event has no type, returning")
            return

        if not data.get("camera_id"):
            _LOGGER.debug("Event %s has no camera ID, returning", event_type)
            return

        if not data.get("home_id"):
            _LOGGER.debug(
                "Event %s for camera %s has no home ID, returning",
                event_type,
                data["camera_id"],
            )
            return

        if (
            data["home_id"] == self.home.entity_id
            and data["camera_id"] == self.device.entity_id
            and event_type == EVENT_TYPE_LIGHT_MODE
        ):
            if data.get("sub_type"):
                self._attr_is_on = bool(data["sub_type"] == "on")
                _LOGGER.debug(
                    "Camera light %s has received light mode with sub_type %s",
                    self.device.name,
                    data["sub_type"],
                )

                self.async_write_ha_state()
            else:
                _LOGGER.debug(
                    "Camera light %s has received light mode event without sub_type",
                    self.device.name,
                )
        else:
            _LOGGER.debug(
                "Camera light %s has received unexpected event as type %s",
                data["camera_id"],
                event_type,
            )

        return

    @property
    def available(self) -> bool:
        """If the webhook is not established, mark as unavailable."""
        return bool(self.data_handler.webhook)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn camera floodlight on."""
        _LOGGER.debug("Turn camera '%s' on", self.device.name)
        await self.device.async_floodlight_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn camera floodlight into auto mode."""
        _LOGGER.debug("Turn camera '%s' to auto mode", self.device.name)
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
            await self.device.async_set_brightness(
                round(kwargs[ATTR_BRIGHTNESS] / 2.55)
            )

        else:
            await self.device.async_on()

        _LOGGER.debug("Turn light '%s' on", self.device.name)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.device.async_off()
        _LOGGER.debug("Turn light '%s' off", self.device.name)
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.on is True

        if (brightness := self.device.brightness) is not None:
            # Netatmo uses a range of [0, 100] to control brightness
            self._attr_brightness = round(brightness * 2.55)
        else:
            self._attr_brightness = None
