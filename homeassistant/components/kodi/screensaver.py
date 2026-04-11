"""Shared Kodi screensaver state."""

from __future__ import annotations

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import Kodi
from pykodi.kodi import KodiHTTPConnection, KodiWSConnection

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import async_signal_screensaver_update


class KodiScreensaver:
    """Shared Kodi screensaver state and events."""

    def __init__(
        self,
        entry_id: str,
        connection: KodiHTTPConnection | KodiWSConnection,
        kodi: Kodi,
    ) -> None:
        """Initialize the shared screensaver state."""
        self._connection = connection
        self._kodi = kodi
        self._signal = async_signal_screensaver_update(entry_id)
        self._hass: HomeAssistant | None = None
        self.is_on: bool | None = None

    @property
    def available(self) -> bool:
        """Return if the underlying Kodi connection is available."""
        return self._connection.connected

    @property
    def signal(self) -> str:
        """Return the dispatcher signal for screensaver updates."""
        return self._signal

    @callback
    def set_hass(self, hass: HomeAssistant) -> None:
        """Store the Home Assistant instance for dispatching updates."""
        self._hass = hass

    @callback
    def _set_state(self, is_on: bool | None) -> None:
        """Set the current screensaver state and notify listeners."""
        if self.is_on == is_on:
            return

        self.is_on = is_on
        if self._hass is not None:
            async_dispatcher_send(self._hass, self._signal)

    async def async_update(self) -> None:
        """Refresh the Kodi screensaver state."""
        if not self._connection.connected:
            self._set_state(None)
            return

        try:
            display_status = await self._kodi.call_method(
                "XBMC.GetInfoBooleans",
                booleans=["System.ScreenSaverActive"],
            )
        except ProtocolError, TransportError:
            self._set_state(None)
            return

        self._set_state(display_status.get("System.ScreenSaverActive"))

    @callback
    def async_clear(self) -> None:
        """Clear the current screensaver state."""
        self._set_state(None)

    @callback
    def async_on_screensaver_on(self, sender, data) -> None:
        """Handle screensaver activation."""
        self._set_state(True)

    @callback
    def async_on_screensaver_off(self, sender, data) -> None:
        """Handle screensaver deactivation."""
        self._set_state(False)

    @callback
    def async_register_ws_callbacks(self) -> None:
        """Register Kodi websocket callbacks."""
        self._connection.server.GUI.OnScreensaverActivated = (
            self.async_on_screensaver_on
        )
        self._connection.server.GUI.OnScreensaverDeactivated = (
            self.async_on_screensaver_off
        )
