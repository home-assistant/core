"""Base entity for Android TV Remote."""
from __future__ import annotations

from androidtvremote2 import AndroidTVRemote, ConnectionClosed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN

PARALLEL_UPDATES = 0


class AndroidTVRemoteBaseEntity(Entity):
    """Android TV Remote Base Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, api: AndroidTVRemote, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._api = api
        self._host = config_entry.data[CONF_HOST]
        self._name = config_entry.data[CONF_NAME]
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
        def is_available_updated(is_available: bool) -> None:
            self._attr_available = is_available
            self.async_write_ha_state()

        @callback
        def is_on_updated(is_on: bool) -> None:
            self._attr_is_on = is_on
            self.async_write_ha_state()

        api.add_is_available_updated_callback(is_available_updated)
        api.add_is_on_updated_callback(is_on_updated)

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
