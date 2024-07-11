"""Base entity for Android TV Remote."""

from __future__ import annotations

from typing import Any

from androidtvremote2 import AndroidTVRemote, ConnectionClosed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_APPS, DOMAIN


class AndroidTVRemoteBaseEntity(Entity):
    """Android TV Remote Base Entity."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, api: AndroidTVRemote, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._api = api
        self._host = config_entry.data[CONF_HOST]
        self._name = config_entry.data[CONF_NAME]
        self._apps: dict[str, Any] = config_entry.options.get(CONF_APPS, {})
        self._attr_unique_id = config_entry.unique_id
        self._attr_is_on = api.is_on
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
    def _is_available_updated(self, is_available: bool) -> None:
        """Update the state when the device is ready to receive commands or is unavailable."""
        self._attr_available = is_available
        self.async_write_ha_state()

    @callback
    def _is_on_updated(self, is_on: bool) -> None:
        """Update the state when device turns on or off."""
        self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._api.add_is_available_updated_callback(self._is_available_updated)
        self._api.add_is_on_updated_callback(self._is_on_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        self._api.remove_is_available_updated_callback(self._is_available_updated)
        self._api.remove_is_on_updated_callback(self._is_on_updated)

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
