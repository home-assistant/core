"""Managing JSON-RPC API connection for all platforms of the Kodi component."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging

from jsonrpc_base.jsonrpc import TransportError
from pykodi import CannotConnectError, InvalidAuthError, Kodi, get_kodi_connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_WS_PORT

WEBSOCKET_WATCHDOG_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


class KodiConnMan:
    """Creates and supervises the connection to a Kodi instance."""

    # Hold list for functions to call on connect and disconnect(error).
    _cb_on_ws_connect: list = []
    _cb_on_ws_disconnect: list = []

    # Will be set when watchdog is created
    _remove_watchdog = None

    def __init__(self, hass, entry: ConfigEntry):
        """Initialize KodiConnMan an its connection."""
        self.connection = get_kodi_connection(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_WS_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_SSL],
            session=async_get_clientsession(hass),
        )
        self._connect_error = False

        # Need Kodi.ping and hass for connection supervision.
        self.kodi = Kodi(self.connection)
        self._hass = hass

    @property
    def connected(self) -> bool:
        """Return kodis connection status."""
        return self.connection.connected

    @property
    def can_subscribe(self) -> bool:
        """Return kodis subscription status."""
        return self.connection.can_subscribe

    async def connect(self) -> bool:
        """Initiate either http or websocket connection."""
        if self.connected:
            _LOGGER.debug("Already connected")
            return True

        try:
            await self.connection.connect()
        except CannotConnectError:
            pass
        except InvalidAuthError as error:
            _LOGGER.error(
                "Login failed: [%s]",
                error,
            )
            return False

        # Kodi component was added to HA without websocket port.
        # Fetching data in poll mode.
        if not self.connection.can_subscribe:
            return True

        _LOGGER.debug("Connected using websockets")
        if self.connected:
            await self._on_ws_connected()

        # Check (kodi.ping) websocket every WEBSOCKET_WATCHDOG_INTERVAL seconds
        async def start_watchdog(event=None):  # pylint: disable=unused-argument
            """Start websocket watchdog."""
            await self._async_connect_websocket_if_disconnected()
            self._remove_watchdog = async_track_time_interval(
                self._hass,
                self._async_connect_websocket_if_disconnected,
                WEBSOCKET_WATCHDOG_INTERVAL,
            )

        # If Home Assistant is already in a running state, start the watchdog
        # immediately, else trigger it after Home Assistant has finished starting.
        if self._hass.state == CoreState.running:
            await start_watchdog()
        else:
            self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, start_watchdog
            )

        return True

    async def close(self):
        """Close Kodi http or websocket connection."""
        _LOGGER.debug("Closing Kodi connection")

        # Invoke callbacks only once
        if self.connected:
            await self._clear_connection()

        try:
            await self.connection.close()
        except (TransportError, CannotConnectError):
            _LOGGER.warning("Unable to close websocket connection")

    async def remove(self):
        """Clean up when component gets removed from home assistant."""
        _LOGGER.debug("Removing Kodi ConnMan")
        if self.connected:
            await self.close()
        if self._remove_watchdog is not None:
            self._remove_watchdog()
        self._cb_on_ws_connect.clear()
        self._cb_on_ws_disconnect.clear()

    async def _on_ws_connected(self):
        """Call after websocket is connected."""
        _LOGGER.debug("Websocket connected")

        # Calling callbacks for ws connected
        for call_back in self._cb_on_ws_connect:
            await call_back()

    async def _on_ws_error(self, close=True):
        """Set websocket connection error condition."""
        if close:
            await self.close()

        if not self._connect_error:
            self._connect_error = True

    async def _clear_connection(self):
        """Clear connection on disconnect or error."""
        # Calling callbacks to clear connection
        for call_back in self._cb_on_ws_disconnect:
            await call_back()

    async def _async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        try:
            await self.connection.connect()
            await self._on_ws_connected()
        except (TransportError, CannotConnectError):
            if not self._connect_error:
                _LOGGER.warning("Unable to connect to Kodi via websocket")
            await self._on_ws_error(False)
        else:
            self._connect_error = False

    async def _ping(self) -> bool:
        """Check connectivity using Kodis buildin ping method."""
        try:
            await self.kodi.ping()
        except (TransportError, CannotConnectError):
            return False
        else:
            return True

    async def _async_connect_websocket_if_disconnected(self, *_):
        """Reconnect the websocket if it fails."""
        if not self.connected:
            await self._async_ws_connect()
        elif not await self._ping():
            if not self._connect_error:
                _LOGGER.warning("Unable to ping Kodi via websocket")
            await self._on_ws_error()
        else:
            self._connect_error = False

    async def add_callback_on_connect(
        self, func: Callable[..., Awaitable[None]]
    ) -> None:
        """Add a function to call when ws is connected."""
        self._cb_on_ws_connect.append(func)

        if not self.connection.can_subscribe:
            return
        # Call callback on add since ws might be already connected
        if self.connection.connected:
            await func()

    async def add_callback_on_disconnect(
        self, func: Callable[..., Awaitable[None]]
    ) -> None:
        """Add a function to call when ws is disconnected."""
        self._cb_on_ws_disconnect.append(func)
