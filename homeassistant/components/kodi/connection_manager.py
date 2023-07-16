"""Managing JSON-RPC API connection for all platforms of the Kodi component."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

from jsonrpc_base.jsonrpc import TransportError
from pykodi import CannotConnectError, InvalidAuthError, Kodi, get_kodi_connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_WS_PORT, DOMAIN

WEBSOCKET_WATCHDOG_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


class KodiConnectionManager:
    """Creates and supervises the connection to a Kodi instance."""

    # Hold list for functions to call on connect and disconnect(error).
    _cb_on_ws_connect: list = []
    _cb_on_ws_disconnect: list = []

    # Will be set when watchdog is created
    _remove_watchdog: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize KodiConnectionManager and its connection."""
        self._connection = get_kodi_connection(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_WS_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_SSL],
            session=async_get_clientsession(hass),
        )

        if (uid := entry.unique_id) is None:
            uid = entry.entry_id
        if (device_name := entry.data[CONF_NAME]) is None:
            device_name = entry.data[CONF_HOST]
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, uid)},
            manufacturer="Kodi",
            name=device_name,
        )

        self._uid = uid
        self._connect_error = False
        # To be able to remove callbacks reliably only once after close
        self._ws_connection_clear = False

        # Need Kodi.ping and hass for connection supervision.
        self.kodi = Kodi(self._connection)
        self._hass = hass

        self._connection_callbacks = {
            "System.OnQuit": self.close,
            "System.OnRestart": self.close,
            "System.OnSleep": self.close,
        }

    @property
    def connected(self) -> bool:
        """Return kodis connection status."""
        return self._connection.connected

    @property
    def can_subscribe(self) -> bool:
        """Return kodis subscription status."""
        return self._connection.can_subscribe

    async def connect(self) -> bool:
        """Initiate either http or websocket connection."""
        if self.connected:
            _LOGGER.debug("Already connected")
            return True

        try:
            await self._connection.connect()
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
        if not self._connection.can_subscribe:
            return True

        _LOGGER.debug("Connected using websockets")
        if self.connected:
            await self._on_ws_connected()

        # The websocket connection must be closed on quit, restart and sleep.
        # Otherwise the jsonrpc library throws an uncatchable TransportError exception
        for api_method, api_callback in self._connection_callbacks.items():
            self.register_websocket_callback(api_method, api_callback)

        # Check (kodi.ping) websocket every WEBSOCKET_WATCHDOG_INTERVAL seconds
        async def start_watchdog(event=None):  # pylint: disable=unused-argument
            """Start websocket watchdog."""
            await self._async_connect_websocket_if_disconnected()
            self._remove_watchdog = async_track_time_interval(
                self._hass,
                self._async_connect_websocket_if_disconnected,
                WEBSOCKET_WATCHDOG_INTERVAL,
            )

        # Making sure that the watchdog is only started once.
        if self._remove_watchdog is None:
            # If Home Assistant is already in a running state, start the watchdog
            # immediately, else trigger it after Home Assistant has finished starting.
            if self._hass.state == CoreState.running:
                await start_watchdog()
            else:
                self._hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, start_watchdog
                )

        return True

    async def close(
        self, sender: str = "", data: str = ""
    ):  # pylint: disable=unused-argument
        """Close Kodi http or websocket connection."""
        _LOGGER.debug("Closing Kodi connection")

        try:
            await self._connection.close()
        except (TransportError, CannotConnectError):
            _LOGGER.warning("Unable to close websocket connection")

        await self._clear_connection()

    async def remove(self):
        """Clean up when component gets removed from home assistant."""
        _LOGGER.debug("Removing Kodi ConnMan")

        if self.connected:
            await self.close()
        if self._remove_watchdog is not None:
            self._remove_watchdog()
            # A websocket connection was used when a watchdog is active.
            # Only then the jsonrpc callbacks need to be unregistered.
            for api_method in self._connection_callbacks:
                self.unregister_websocket_callback(api_method)

        self._cb_on_ws_connect.clear()
        self._cb_on_ws_disconnect.clear()

    async def _on_ws_connected(self):
        """Call after websocket is connected."""
        _LOGGER.debug("Websocket connected")
        self._ws_connection_clear = False

        version = (await self.kodi.get_application_properties(["version"]))["version"]
        sw_version = f"{version['major']}.{version['minor']}"
        dev_reg = dr.async_get(self._hass)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, self._uid)})
        dev_reg.async_update_device(device.id, sw_version=sw_version)

        # Calling websocket connected callbacks
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
        if self._ws_connection_clear:
            return
        self._ws_connection_clear = True

        # Calling websocket disconnect callbacks if supported
        if self.can_subscribe:
            for call_back in self._cb_on_ws_disconnect:
                await call_back()

    async def _async_ws_connect(self):
        """Connect to Kodi via websocket protocol."""
        try:
            await self._connection.connect()
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

    async def _ws_callback_dummy(self, sender: Any, data: Any) -> None:
        """Use to 'unregister' websocket callbacks.

        Since jsonrpc_base doesn't offer an unregister method, an
        empty function is used as a replacement.
        """

    def register_websocket_callback(
        self, api_method: str, func: Callable[[Any, Any], Awaitable[None]]
    ) -> None:
        """Register a callback for a websocket server request."""
        setattr(self._connection.server, api_method, func)

    def unregister_websocket_callback(self, api_method: str) -> None:
        """Unregister a callback for a websocket server request."""
        setattr(self._connection.server, api_method, self._ws_callback_dummy)

        # del self._connection.server._server_request_handlers[method_name]
        # would also work, but access to a protected member is bad practice
        # and also gives a lint error.

    async def add_callback_on_connect(
        self, func: Callable[..., Awaitable[None]]
    ) -> None:
        """Add a function to call when ws is connected."""
        self._cb_on_ws_connect.append(func)

        if not self._connection.can_subscribe:
            return
        # Call callback when added since ws might be already connected
        if self._connection.connected:
            await func()

    async def add_callback_on_disconnect(
        self, func: Callable[..., Awaitable[None]]
    ) -> None:
        """Add a function to call when ws is disconnected."""
        self._cb_on_ws_disconnect.append(func)


class KodiConnectionClient(Entity):
    """Base class to be used by Kodi platforms."""

    _attr_has_entity_name = True

    def __init__(
        self,
        connman: KodiConnectionManager,
        ws_callbacks: dict[str, Callable[[Any, Any], Awaitable[None]]] | None = None,
    ) -> None:
        """Initialize Kodi base class for platforms."""
        self._connman = connman
        self._websocket_callbacks = ws_callbacks if not None else {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._connman._uid)},
        )

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return not self._connman.can_subscribe

    def _reset_state(self) -> None:
        """Run on webocket disconnect to reset the entity state.

        To be extended by integrations.
        """

    async def async_added_to_hass(self) -> None:
        """Register callbacks for needed api endpoints."""
        await self._connman.add_callback_on_connect(self._on_ws_connected)
        await self._connman.add_callback_on_disconnect(self._on_ws_disconnected)

    @callback
    async def _on_ws_connected(self):
        """Call after websocket is connected."""
        _LOGGER.debug("Kodi connection %s websocket connected", self.name)

        # Run entity update method on connect
        self.async_schedule_update_ha_state(True)
        for api_method, api_callback in self._websocket_callbacks.items():
            self._connman.register_websocket_callback(api_method, api_callback)

    @callback
    async def _on_ws_disconnected(self):
        """Call after websocket is connected."""
        for api_method in self._websocket_callbacks:
            self._connman.unregister_websocket_callback(api_method)
        self._reset_state()
        self.async_write_ha_state()
