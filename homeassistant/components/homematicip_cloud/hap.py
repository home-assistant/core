"""Access point for the HomematicIP Cloud component."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
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

    # Bounded wait for websocket reconnect before refreshing state.
    _WS_WAIT_INTERVAL = 2
    _WS_WAIT_WARNING = 60
    _WS_WAIT_TIMEOUT = 120

    # Staleness detection thresholds. The library has its own 8h safety net;
    # we surface staleness much earlier so users see a clear log signal and
    # we capture diagnostics for the still-unsolved reports in core #160048.
    _STALE_CHECK_INTERVAL = timedelta(minutes=1)
    _STALE_WARNING_SECONDS = 300
    _STALE_ERROR_SECONDS = 600

    def __init__(
        self, hass: HomeAssistant, config_entry: HomematicIPConfigEntry
    ) -> None:
        """Initialize HomematicIP Cloud connection."""
        self.hass = hass
        self.config_entry = config_entry

        self._ws_close_requested = False
        self._ws_connection_closed = asyncio.Event()
        self._get_state_task: asyncio.Task | None = None
        self._stale_check_unsub: CALLBACK_TYPE | None = None
        self._stale_warning_logged = False
        self._stale_error_logged = False
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

        self._stale_check_unsub = async_track_time_interval(
            self.hass,
            self._async_check_websocket_staleness,
            self._STALE_CHECK_INTERVAL,
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
            _LOGGER.info(
                "HMIP access point has reconnected to the cloud (%s)",
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

    def _websocket_diagnostic_context(self) -> str:
        """Return a single-line summary of websocket diagnostics for logs."""
        diagnostics = {
            "last_disconnect_reason": self.home.websocket_last_disconnect_reason(),
            "reconnect_attempts": self.home.websocket_reconnect_attempt_count(),
            "seconds_since_last_message": (
                self.home.websocket_seconds_since_last_message()
            ),
            "message_count": self.home.websocket_message_count(),
        }
        rendered = ", ".join(
            f"{key}={value!r}"
            for key, value in diagnostics.items()
            if value is not None
        )
        return rendered or "no diagnostics available"

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

    async def _wait_for_websocket_connection(self) -> bool:
        """Wait up to ``_WS_WAIT_TIMEOUT`` seconds for the websocket to be connected.

        Returns ``True`` when the websocket reports connected, ``False`` when the
        wait times out. Even on timeout we proceed with ``get_state``: the REST
        call is independent and may still recover the entity state.
        """
        elapsed = 0
        warning_logged = False

        while not self.home.websocket_is_connected():
            if elapsed >= self._WS_WAIT_TIMEOUT:
                _LOGGER.warning(
                    "Websocket did not reconnect within %s seconds; "
                    "proceeding with HomematicIP state refresh anyway (%s)",
                    self._WS_WAIT_TIMEOUT,
                    self._websocket_diagnostic_context(),
                )
                return False
            await asyncio.sleep(self._WS_WAIT_INTERVAL)
            elapsed += self._WS_WAIT_INTERVAL
            # Re-check connectivity before logging so a reconnect during the
            # sleep does not produce a misleading "still waiting" warning.
            if (
                not warning_logged
                and elapsed >= self._WS_WAIT_WARNING
                and not self.home.websocket_is_connected()
            ):
                warning_logged = True
                _LOGGER.warning(
                    "Still waiting for HomematicIP websocket reconnect after "
                    "%s seconds (%s)",
                    elapsed,
                    self._websocket_diagnostic_context(),
                )

        return True

    async def _try_get_state(self) -> None:
        """Call get_state in a loop until no error occurs.

        Uses exponential backoff on error.
        """

        await self._wait_for_websocket_connection()

        delay = 8
        max_delay = 1500
        while True:
            try:
                await self.get_state()
                break
            except HmipAuthenticationError:
                _LOGGER.error(
                    "Authentication error from HomematicIP Cloud, triggering reauth"
                )
                self.config_entry.async_start_reauth(self.hass)
                break
            except HmipConnectionError as err:
                _LOGGER.warning(
                    "Get_state failed, retrying in %s seconds: %s", delay, err
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception(
                    "Unexpected error updating state after HomematicIP "
                    "reconnect, retrying in %s seconds (%s)",
                    delay,
                    self._websocket_diagnostic_context(),
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    @callback
    def _async_check_websocket_staleness(self, _now: datetime) -> None:
        """Detect a websocket that claims connected but has stopped receiving.

        The library's stale-connection safety net only triggers after 8h.
        Surfacing this much earlier gives users a clear log signal and
        captures diagnostics for the still-unsolved reports in core #160048.
        """
        if not self.home.websocket_is_connected():
            return

        seconds_since = self.home.websocket_seconds_since_last_message()
        if seconds_since is None:
            return

        if seconds_since < self._STALE_WARNING_SECONDS:
            self._stale_warning_logged = False
            self._stale_error_logged = False
            return

        if seconds_since >= self._STALE_ERROR_SECONDS:
            if not self._stale_error_logged:
                _LOGGER.error(
                    "HomematicIP websocket has not received a message for "
                    "%.0f seconds while reporting connected (%s)",
                    seconds_since,
                    self._websocket_diagnostic_context(),
                )
                self._stale_error_logged = True
            return

        if not self._stale_warning_logged:
            _LOGGER.warning(
                "HomematicIP websocket has not received a message for "
                "%.0f seconds while reporting connected (%s)",
                seconds_since,
                self._websocket_diagnostic_context(),
            )
            self._stale_warning_logged = True

    async def get_state(self) -> None:
        """Update HMIP state and tell Home Assistant."""
        await self.home.get_current_state_async()
        # ``set_all_to_unavailable`` marked every device unreach=True on
        # disconnect; ``get_current_state_async`` only clears that flag for
        # devices whose state actually changed during the outage, so the rest
        # stay stuck unavailable after reconnect. Force-clear for all devices.
        # Trade-off: a device that is *genuinely* unreachable on the cloud
        # side will briefly appear available until its next state push
        # corrects it. That self-corrects, while the previous behaviour left
        # entities stuck unavailable indefinitely (core #160048).
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

    async def async_reset(self) -> bool:
        """Close the websocket connection."""
        self._ws_close_requested = True
        if self._stale_check_unsub is not None:
            self._stale_check_unsub()
            self._stale_check_unsub = None
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
        _LOGGER.warning(
            "Websocket connection to HomematicIP Cloud closed (%s)",
            self._websocket_diagnostic_context(),
        )
        self._ws_connection_closed.set()
        # Re-arm staleness logging so a new stuck period after reconnect
        # is reported instead of being squelched by a previous one.
        self._stale_warning_logged = False
        self._stale_error_logged = False

    async def ws_reconnected_handler(self, reason: str) -> None:
        """Handle websocket reconnection."""
        _LOGGER.info(
            "Websocket connection to HomematicIP Cloud trying to reconnect due to "
            "reason: %s (%s)",
            reason,
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
