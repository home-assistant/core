"""Remote control support for Android TV Remote."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from androidtvremote2 import AndroidTVRemote, ConnectionClosed

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV remote entity based on a config entry."""
    api: AndroidTVRemote = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AndroidTVRemoteEntity(api, config_entry)])


class AndroidTVRemoteEntity(RemoteEntity):
    """Representation of an Android TV Remote."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, api: AndroidTVRemote, config_entry: ConfigEntry) -> None:
        """Initialize device."""
        self._api = api
        self._host = config_entry.data[CONF_HOST]
        self._name = config_entry.data[CONF_NAME]
        self._attr_unique_id = config_entry.unique_id
        self._attr_supported_features = RemoteEntityFeature.ACTIVITY
        self._attr_is_on = api.is_on
        self._attr_current_activity = api.current_app
        device_info = api.device_info
        assert config_entry.unique_id
        assert device_info
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, config_entry.data[CONF_MAC])},
            identifiers={(DOMAIN, config_entry.unique_id)},
            name=self._name,
            manufacturer=device_info["manufacturer"],
            model=device_info["model"],
        )

        @callback
        def is_on_updated(is_on: bool) -> None:
            self._attr_is_on = is_on
            self.async_write_ha_state()

        @callback
        def current_app_updated(current_app: str) -> None:
            self._attr_current_activity = current_app
            self.async_write_ha_state()

        @callback
        def is_available_updated(is_available: bool) -> None:
            if is_available:
                _LOGGER.info(
                    "Reconnected to %s at %s",
                    self._name,
                    self._host,
                )
            else:
                _LOGGER.warning(
                    "Disconnected from %s at %s",
                    self._name,
                    self._host,
                )
            self._attr_available = is_available
            self.async_write_ha_state()

        api.add_is_on_updated_callback(is_on_updated)
        api.add_current_app_updated_callback(current_app_updated)
        api.add_is_available_updated_callback(is_available_updated)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the Android TV on."""
        if not self.is_on:
            self._send_key_command("POWER")
        activity = kwargs.get(ATTR_ACTIVITY, "")
        if activity:
            self._send_launch_app_command(activity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the Android TV off."""
        if self.is_on:
            self._send_key_command("POWER")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        hold_secs = kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS)

        for _ in range(num_repeats):
            for single_command in command:
                if hold_secs:
                    self._send_key_command(single_command, "START_LONG")
                    await asyncio.sleep(hold_secs)
                    self._send_key_command(single_command, "END_LONG")
                else:
                    self._send_key_command(single_command, "SHORT")
                await asyncio.sleep(delay_secs)

    def _send_key_command(self, key_code: str, direction: str = "SHORT") -> None:
        """Send a key press to Android TV.

        This does not block; it buffers the data and arranges for it to be sent out asynchronously.
        """
        try:
            self._api.send_key_command(key_code, direction)
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                "Connection to Android TV device is closed"
            ) from exc

    def _send_launch_app_command(self, app_link: str) -> None:
        """Launch an app on Android TV.

        This does not block; it buffers the data and arranges for it to be sent out asynchronously.
        """
        try:
            self._api.send_launch_app_command(app_link)
        except ConnectionClosed as exc:
            raise HomeAssistantError(
                "Connection to Android TV device is closed"
            ) from exc
