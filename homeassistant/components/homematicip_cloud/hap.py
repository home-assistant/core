"""Access point for the HomematicIP Cloud integration."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from homematicip.async_home import AsyncHome
from homematicip.auth import Auth
from homematicip.base.enums import EventType
from homematicip.connection.connection_context import ConnectionContextBuilder
from homematicip.connection.rest_connection import RestConnection
from homematicip.exceptions.connection_exceptions import (
    HmipAuthenticationError,
    HmipConnectionError,
)

import homeassistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import HMIPC_AUTHTOKEN, HMIPC_HAPID, HMIPC_NAME, HMIPC_PIN, PLATFORMS
from .errors import HmipcConnectionError

_LOGGER = logging.getLogger(__name__)

type HomematicIPConfigEntry = ConfigEntry[HomematicipHAP]


async def build_context_async(
    hass: HomeAssistant, hapid: str | None, authtoken: str | None
):
    """Create a HomematicIP context object."""
    ssl_ctx = homeassistant.util.ssl.get_default_context()
    client_session = get_async_client(hass)

    return await ConnectionContextBuilder.build_context_async(
        accesspoint_id=hapid,
        auth_token=authtoken,
        ssl_ctx=ssl_ctx,
        httpx_client_session=client_session,
    )


class HomematicipAuth:
    """Manages HomematicIP client registration."""

    auth: Auth

    def __init__(self, hass: HomeAssistant, config: dict[str, str]) -> None:
        """Initialize HomematicIP Cloud client registration."""
        self.hass = hass
        self.config = config

    async def async_setup(self) -> bool:
        """Connect to HomematicIP for registration."""
        try:
            self.auth = await self.get_auth(
                self.hass, self.config.get(HMIPC_HAPID), self.config.get(HMIPC_PIN)
            )
        except HmipcConnectionError:
            return False
        return self.auth is not None

    async def async_checkbutton(self) -> bool:
        """Check blue butten has been pressed."""
        try:
            return await self.auth.is_request_acknowledged()
        except HmipConnectionError:
            return False

    async def async_register(self):
        """Register client at HomematicIP."""
        try:
            authtoken = await self.auth.request_auth_token()
            await self.auth.confirm_auth_token(authtoken)
        except HmipConnectionError:
            return False
        return authtoken

    async def get_auth(self, hass: HomeAssistant, hapid, pin):
        """Create a HomematicIP access point object."""
        context = await build_context_async(hass, hapid, None)
        connection = RestConnection(
            context,
            log_status_exceptions=False,
            httpx_client_session=get_async_client(hass),
        )
        # hass.loop
        auth = Auth(connection, context.client_auth_token, hapid)

        try:
            auth.set_pin(pin)
            result = await auth.connection_request(hapid)
            _LOGGER.debug("Connection request result: %s", result)
        except HmipConnectionError:
            return None
        return auth


class HomematicipHAP:
    """Manages HomematicIP HTTP and WebSocket connection."""

    home: AsyncHome

    def __init__(
        self, hass: HomeAssistant, config_entry: HomematicIPConfigEntry
    ) -> None:
        """Initialize HomematicIP Cloud connection."""
        self.hass = hass
        self.config_entry = config_entry

        self._ws_close_requested = False
        self._ws_connection_closed = asyncio.Event()
        self._get_state_task: asyncio.Task | None = None
        self.hmip_device_by_entity_id: dict[str, Any] = {}
        self.reset_connection_listener: Callable | None = None

    async def async_setup(self, tries: int = 0) -> bool:
        """Initialize connection."""
        try:
            self.home = await self.get_hap(
                self.hass,
                self.config_entry.data.get(HMIPC_HAPID),
                self.config_entry.data.get(HMIPC_AUTHTOKEN),
                self.config_entry.data.get(HMIPC_NAME),
            )

        except HmipcConnectionError as err:
            raise ConfigEntryNotReady from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error connecting with HomematicIP Cloud: %s", err)
            return False

        _LOGGER.debug(
            "Connected to HomematicIP with HAP %s", self.config_entry.unique_id
        )

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

        return True

    @callback
    def async_update(self, *args, **kwargs) -> None:
        """Async update the home device.

        Triggered when the HMIP HOME_CHANGED event has fired.
        There are several occasions for this event to happen.
        1. We are interested to check whether the access point
        is still connected. If not, entity state changes cannot
        be forwarded to hass. So if access point is disconnected all devices
        are set to unavailable.
        2. We need to update home including devices and groups after a reconnect.
        3. We need to update home without devices and groups in all other cases.

        """
        if not self.home.connected:
            _LOGGER.error("HMIP access point has lost connection with the cloud")
            self._ws_connection_closed.set()
            self.set_all_to_unavailable()
        elif self._ws_connection_closed.is_set():
            _LOGGER.info("HMIP access point has reconnected to the cloud")
            _LOGGER.debug(
                "HMIP websocket diagnostics: %s",
                self._websocket_diagnostic_context(),
            )
            self._start_get_state_task()

    @callback
    def async_create_entity(self, *args, **kwargs) -> None:
        """Create an entity or a group."""
        is_device = EventType(kwargs["event_type"]) == EventType.DEVICE_ADDED
        self.hass.async_create_task(self.async_create_entity_lazy(is_device))

    async def async_create_entity_lazy(self, is_device=True) -> None:
        """Delay entity creation to allow the user to enter a device name."""
        if is_device:
            await asyncio.sleep(30)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    def websocket_diagnostics(self) -> dict[str, Any]:
        """Return websocket diagnostics dict (None values omitted)."""
        diagnostics = {
            "last_disconnect_reason": self.home.websocket_last_disconnect_reason(),
            "reconnect_attempts": self.home.websocket_reconnect_attempt_count(),
            "seconds_since_last_message": (
                self.home.websocket_seconds_since_last_message()
            ),
            "message_count": self.home.websocket_message_count(),
        }
        return {k: v for k, v in diagnostics.items() if v is not None}

    def _websocket_diagnostic_context(self) -> str:
        """Return a single-line summary of websocket diagnostics for logs."""
        diagnostics = self.websocket_diagnostics()
        if not diagnostics:
            return "no diagnostics available"
        return ", ".join(f"{k}={v!r}" for k, v in diagnostics.items())

    @callback
    def _start_get_state_task(self) -> None:
        """Cancel any in-flight reconnect refresh and start a new one."""
        if self._get_state_task is not None and not self._get_state_task.done():
            _LOGGER.debug(
                "Cancelling previous HomematicIP reconnect state refresh task"
            )
            self._get_state_task.cancel()

        self._get_state_task = self.hass.async_create_task(self._try_get_state())
        self._get_state_task.add_done_callback(self.get_state_finished)
        self._ws_connection_closed.clear()

    async def _try_get_state(self) -> None:
        """Refresh state after a websocket reconnect.

        Delegates the bounded websocket wait + retry-with-exponential-backoff
        to the homematicip library (``refresh_state_after_reconnect_async``),
        and only handles HA-specific concerns here:
        - on authentication failure, trigger reauth
        - clear the per-device ``unreach`` flag and signal entity updates
          (the workaround for core#160048)
        """
        try:
            await self.home.refresh_state_after_reconnect_async()
        except HmipAuthenticationError:
            _LOGGER.error(
                "Authentication error from HomematicIP Cloud, triggering reauth"
            )
            self.config_entry.async_start_reauth(self.hass)
            return
        self._post_state_refresh()

    async def _on_websocket_stale(self, severity: str, seconds_since: float) -> None:
        """Log a websocket-stale event surfaced by the library.

        The library polls staleness internally and fires this callback once
        per severity per stuck period; it re-arms when fresh messages arrive.
        We just translate severity to a log level.
        """
        log = _LOGGER.error if severity == "error" else _LOGGER.warning
        log(
            "HomematicIP websocket has not received a message for "
            "%.0f seconds while reporting connected",
            seconds_since,
        )
        _LOGGER.debug(
            "HMIP websocket diagnostics: %s",
            self._websocket_diagnostic_context(),
        )

    async def get_state(self) -> None:
        """Update HMIP state and tell Home Assistant."""
        await self.home.get_current_state_async()
        self._post_state_refresh()

    def _post_state_refresh(self) -> None:
        """Apply HA-specific post-processing after a state refresh.

        ``set_all_to_unavailable`` marked every device unreach=True on
        disconnect; ``get_current_state_async`` only clears that flag for
        devices whose state actually changed during the outage, so the rest
        stay stuck unavailable after reconnect. Force-clear for all devices.
        Trade-off: a device that is *genuinely* unreachable on the cloud
        side will briefly appear available until its next state push
        corrects it. That self-corrects, while the previous behaviour left
        entities stuck unavailable indefinitely (core #160048).
        """
        for device in self.home.devices:
            device.unreach = False
        self.update_all()

    def get_state_finished(self, future) -> None:
        """Execute when try_get_state coroutine has finished."""
        try:
            future.result()
        except asyncio.CancelledError:
            _LOGGER.debug("HomematicIP reconnect state refresh task was cancelled")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error updating state after HMIP access point reconnect: %s", err
            )
        else:
            _LOGGER.info(
                "Updating state after HMIP access point"
                " reconnect finished successfully",
            )

    def set_all_to_unavailable(self) -> None:
        """Set all devices to unavailable and tell Home Assistant."""
        for device in self.home.devices:
            device.unreach = True
        self.update_all()

    def update_all(self) -> None:
        """Signal all devices to update their state."""
        for device in self.home.devices:
            device.fire_update_event()

    async def async_connect(self, home: AsyncHome) -> None:
        """Connect to HomematicIP Cloud Websocket."""
        await home.enable_events()

        home.set_on_connected_handler(self.ws_connected_handler)
        home.set_on_disconnected_handler(self.ws_disconnected_handler)
        home.set_on_reconnect_handler(self.ws_reconnected_handler)
        home.set_on_websocket_stale_handler(self._on_websocket_stale)

    async def async_reset(self) -> bool:
        """Close the websocket connection."""
        self._ws_close_requested = True
        if self._get_state_task is not None:
            self._get_state_task.cancel()
        await self.home.disable_events_async()
        _LOGGER.debug("Closed connection to HomematicIP cloud server")
        await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )
        self.hmip_device_by_entity_id = {}
        return True

    @callback
    def shutdown(self, event) -> None:
        """Wrap the call to async_reset.

        Used as an argument to EventBus.async_listen_once.
        """
        self.hass.async_create_task(self.async_reset())
        _LOGGER.debug(
            "Reset connection to access point id %s", self.config_entry.unique_id
        )

    async def ws_connected_handler(self) -> None:
        """Handle websocket connected."""
        _LOGGER.info("Websocket connection to HomematicIP Cloud established")
        if self._ws_connection_closed.is_set():
            self._start_get_state_task()

    async def ws_disconnected_handler(self) -> None:
        """Handle websocket disconnection."""
        _LOGGER.warning("Websocket connection to HomematicIP Cloud closed")
        _LOGGER.debug(
            "HMIP websocket diagnostics: %s",
            self._websocket_diagnostic_context(),
        )
        self._ws_connection_closed.set()

    async def ws_reconnected_handler(self, reason: str) -> None:
        """Handle websocket reconnection."""
        _LOGGER.info(
            "Websocket connection to HomematicIP Cloud trying to reconnect due to "
            "reason: %s",
            reason,
        )
        _LOGGER.debug(
            "HMIP websocket diagnostics: %s",
            self._websocket_diagnostic_context(),
        )

        self._ws_connection_closed.set()

    async def get_hap(
        self,
        hass: HomeAssistant,
        hapid: str | None,
        authtoken: str | None,
        name: str | None,
    ) -> AsyncHome:
        """Create a HomematicIP access point object."""
        home = AsyncHome()

        home.name = name
        # Use the title of the config entry as title for the home.
        home.label = self.config_entry.title
        home.modelType = "HomematicIP Cloud Home"

        try:
            context = await build_context_async(hass, hapid, authtoken)
            home.init_with_context(context, True, get_async_client(hass))
            await home.get_current_state_async()
        except HmipConnectionError as err:
            raise HmipcConnectionError from err
        home.on_update(self.async_update)
        home.on_create(self.async_create_entity)

        await self.async_connect(home)

        return home
