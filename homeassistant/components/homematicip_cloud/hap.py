"""Access point for the HomematicIP Cloud component."""
# Debug build: lackas/hmip-reconnect-fix v10 (2026-04-02)

from __future__ import annotations

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
        _LOGGER.debug("HomematicIP Cloud HAP starting — debug build v10 (2026-04-02)")
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
            "Connected to HomematicIP with HAP %s — %d devices loaded",
            self.config_entry.unique_id,
            len(list(self.home.devices)),
        )

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

        devices = list(self.home.devices)
        listeners_total = sum(len(getattr(d, "_on_update", [])) for d in devices)
        _LOGGER.debug(
            "async_setup complete — %d devices, %d total listeners registered",
            len(devices),
            listeners_total,
        )

        # Start hourly entity state dump for debugging
        self.hass.async_create_task(self._hourly_state_dump())

        return True

    async def _hourly_state_dump(self) -> None:
        """Log hmip entity availability every hour for debugging."""
        while True:
            await asyncio.sleep(3600)
            self._log_entity_state_snapshot("hourly")

    def _log_entity_state_snapshot(self, trigger: str, since_reconnect: bool = False) -> None:
        """Log current hmip entity states, orphaned devices, and state mismatches."""
        try:
            from homeassistant.const import STATE_UNAVAILABLE, STATE_ON, STATE_OFF
            all_states = self.hass.states.async_all()
            hmip_states = [s for s in all_states if s.entity_id.startswith(f"{self.config_entry.domain}.")]
            unavailable = [s.entity_id for s in hmip_states if s.state == STATE_UNAVAILABLE]
            devices = list(self.home.devices)
            orphaned = [d for d in devices if not getattr(d, "_on_update", [])]
            now = self.hass.util.dt.utcnow()

            # Stale: entities whose last_changed is older than 10 min (catches wrong-value stale)
            stale = [
                (s.entity_id, s.state, str(s.last_changed)[:16] if s.last_changed else "?")
                for s in hmip_states
                if s.last_changed and (now - s.last_changed).total_seconds() > 600
                and s.state not in (STATE_UNAVAILABLE,)
            ]

            # State mismatch: compare library device state vs HA entity state
            mismatches = []
            for device in devices:
                for ch_idx, channel in (getattr(device, "functionalChannels", {}) or {}).items():
                    lib_on = getattr(channel, "on", None)
                    if lib_on is None:
                        continue
                    # Find HA entities for this device
                    device_id = getattr(device, "id", None)
                    if not device_id:
                        continue
                    for s in hmip_states:
                        uid = getattr(self.hass.states.get(s.entity_id), "attributes", {}).get("unique_id")
                        ha_on = s.state == STATE_ON
                        if lib_on != ha_on and s.state not in (STATE_UNAVAILABLE,):
                            if device_id in s.entity_id or (device.label and device.label.lower().replace(" ", "_") in s.entity_id):
                                mismatches.append(
                                    f"{s.entity_id}: HA={s.state} lib={'on' if lib_on else 'off'}"
                                )

            _LOGGER.debug(
                "[%s] %d hmip entities | %d unavailable: %s | %d orphaned: %s | %d stale>10min: %s | %d mismatches: %s",
                trigger,
                len(hmip_states),
                len(unavailable),
                [e.split(".", 1)[1] for e in unavailable[:10]],
                len(orphaned),
                [getattr(d, "label", "?") for d in orphaned],
                len(stale),
                [(e.split(".", 1)[1], v, t) for e, v, t in stale[:5]],
                len(mismatches),
                mismatches[:5],
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("_log_entity_state_snapshot(%s) failed", trigger)

    async def _ws_push_watchdog(self) -> None:
        """Watchdog: if WS is connected but no push events for 10min, force reconnect."""
        import time
        SILENCE_THRESHOLD = 600  # 10 minutes
        CHECK_INTERVAL = 120     # check every 2 minutes
        await asyncio.sleep(300)  # initial grace period after startup
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            if self._ws_close_requested:
                return
            ws_client = getattr(self.home, "_websocket_client", None)
            if ws_client is None or not ws_client.is_connected():
                continue  # not connected, library will handle reconnect
            last_msg = getattr(self, "_last_ws_message_time", 0.0)
            silence = time.monotonic() - last_msg if last_msg > 0 else None
            if silence is not None and silence > SILENCE_THRESHOLD:
                _LOGGER.warning(
                    "WS push watchdog: no push events for %.0fs while connected — forcing reconnect",
                    silence,
                )
                # Force reconnect by stopping and restarting the WS client
                await ws_client.stop()
                self._last_ws_message_time = time.monotonic()  # reset to avoid loop
                await self.home.enable_events()
                _LOGGER.info("WS push watchdog: reconnect triggered")
            elif silence is not None:
                _LOGGER.debug(
                    "WS push watchdog: last frame %.0fs ago (threshold=%ds)",
                    silence,
                    SILENCE_THRESHOLD,
                )

    async def _post_reconnect_check(self) -> None:
        """60s after reconnect: log state snapshot and fire update_all as safety net."""
        await asyncio.sleep(60)
        _LOGGER.debug("post-reconnect check (60s after get_state succeeded)")
        self._log_entity_state_snapshot("post-reconnect-60s")
        # Safety net: fire update_all again in case some entities missed the first round
        _LOGGER.debug("post-reconnect safety net: firing update_all again")
        self.update_all(after_reconnect=True)

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
                "HMIP access point has reconnected to the cloud (via HOME_CHANGED event)"
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

    @callback
    def _start_get_state_task(self) -> None:
        """Cancel any existing get_state task and start a new one."""
        if self._get_state_task is not None and not self._get_state_task.done():
            _LOGGER.debug("Cancelling existing get_state task before starting new one")
            self._get_state_task.cancel()
        _LOGGER.debug(
            "Starting get_state task (ws_closed_event=%s)",
            self._ws_connection_closed.is_set(),
        )
        self._get_state_task = self.hass.async_create_task(self._try_get_state())
        self._get_state_task.add_done_callback(self.get_state_finished)
        self._ws_connection_closed.clear()

    _WS_WAIT_TIMEOUT = 300  # seconds before giving up waiting for WS reconnect

    async def _try_get_state(self) -> None:
        """Call get_state in a loop until no error occurs, using exponential backoff on error."""

        # Wait until WebSocket connection is established, with a timeout.
        # If the WS never reconnects, proceed anyway — get_state will fail and retry.
        _LOGGER.debug("Waiting for WebSocket connection before get_state")
        ws_wait_elapsed = 0
        while not self.home.websocket_is_connected():
            await asyncio.sleep(2)
            ws_wait_elapsed += 2
            if ws_wait_elapsed % 30 == 0:
                _LOGGER.debug(
                    "Still waiting for WebSocket connection (%ds elapsed, timeout=%ds)",
                    ws_wait_elapsed,
                    self._WS_WAIT_TIMEOUT,
                )
            if ws_wait_elapsed >= self._WS_WAIT_TIMEOUT:
                _LOGGER.warning(
                    "WebSocket did not reconnect within %ds — proceeding with get_state anyway",
                    self._WS_WAIT_TIMEOUT,
                )
                break
        _LOGGER.debug(
            "WebSocket connected=%s, proceeding with get_state",
            self.home.websocket_is_connected(),
        )

        delay = 8
        max_delay = 1500
        while True:
            try:
                _LOGGER.debug("Calling get_state")
                await self.get_state()
                _LOGGER.debug("get_state succeeded")
                # Schedule post-reconnect check: log state + safety-net update_all after 60s
                self.hass.async_create_task(self._post_reconnect_check())
                break
            except asyncio.CancelledError:
                raise
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
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Unexpected error during get_state, retrying in %s seconds",
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    async def get_state(self) -> None:
        """Update HMIP state and tell Home Assistant."""
        devices_before = list(self.home.devices)
        sample_id_before = id(devices_before[0]) if devices_before else None
        _LOGGER.debug(
            "get_state: before get_current_state_async — %d devices, sample_id=%s",
            len(devices_before),
            sample_id_before,
        )
        await self.home.get_current_state_async()
        devices_after = list(self.home.devices)
        sample_id_after = id(devices_after[0]) if devices_after else None
        _LOGGER.debug(
            "get_state: after get_current_state_async — %d devices, sample_id=%s, instances_replaced=%s",
            len(devices_after),
            sample_id_after,
            sample_id_before != sample_id_after,
        )
        # Reset unreach flag on all devices so entities become available again.
        # set_all_to_unavailable() sets unreach=True on disconnect; get_current_state
        # only clears it for devices whose state actually changed. Force-clear all.
        for device in devices_after:
            device.unreach = False
        _LOGGER.debug("get_state: calling update_all() on %d devices", len(devices_after))
        self.update_all(after_reconnect=True)

    def get_state_finished(self, future) -> None:
        """Execute when try_get_state coroutine has finished."""
        try:
            future.result()
        except asyncio.CancelledError:
            _LOGGER.debug("Get_state task was cancelled")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error updating state after HMIP access point reconnect: %s", err
            )
        else:
            _LOGGER.info(
                "Updating state after HMIP access point reconnect finished successfully",
            )

    def set_all_to_unavailable(self) -> None:
        """Set all devices to unavailable and tell Home Assistant."""
        devices = list(self.home.devices)
        _LOGGER.debug("set_all_to_unavailable: marking %d devices unreachable", len(devices))
        for device in devices:
            device.unreach = True
        self.update_all()

    def update_all(self, after_reconnect: bool = False) -> None:
        """Signal all devices to update their state."""
        devices = list(self.home.devices)
        if after_reconnect:
            # Only log listener details on reconnect — too noisy for normal operation
            listeners_total = sum(len(getattr(d, "_on_update", [])) for d in devices)
            orphaned_devices = [d for d in devices if not getattr(d, "_on_update", [])]
            _LOGGER.debug(
                "update_all (reconnect): %d devices, %d total listeners, %d orphaned",
                len(devices),
                listeners_total,
                len(orphaned_devices),
            )
            for device in orphaned_devices:
                _LOGGER.warning(
                    "update_all: orphaned device (no HA listeners) — id=%s label=%r type=%s",
                    getattr(device, "id", "?"),
                    getattr(device, "label", "?"),
                    type(device).__name__,
                )
        for device in devices:
            device.fire_update_event()

    async def async_connect(self, home: AsyncHome) -> None:
        """Connect to HomematicIP Cloud Websocket."""
        await home.enable_events()

        home.set_on_connected_handler(self.ws_connected_handler)
        home.set_on_disconnected_handler(self.ws_disconnected_handler)
        home.set_on_reconnect_handler(self.ws_reconnected_handler)

        # Monkey-patch: wrap the library's _listen() to log raw WS frames
        # and update a last-received timestamp for the watchdog.
        self._last_ws_message_time: float = 0.0
        ws_client = getattr(home, "_websocket_client", None)
        if ws_client is not None:
            original_handle_ws_message = ws_client._handle_ws_message

            async def _patched_handle_ws_message(message):
                import time
                self._last_ws_message_time = time.monotonic()
                _LOGGER.debug(
                    "WS raw frame received (len=%d): %s",
                    len(message),
                    message[:120] if isinstance(message, str) else str(message)[:120],
                )
                await original_handle_ws_message(message)

            ws_client._handle_ws_message = _patched_handle_ws_message
            _LOGGER.debug("WS frame logging monkey-patch applied")

        # Start the push-event watchdog
        self.hass.async_create_task(self._ws_push_watchdog())

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
        _LOGGER.info(
            "Websocket connection to HomematicIP Cloud established (ws_closed_event=%s)",
            self._ws_connection_closed.is_set(),
        )
        if self._ws_connection_closed.is_set():
            _LOGGER.debug("ws_closed_event is set — starting get_state task")
            self._start_get_state_task()
        else:
            _LOGGER.debug("ws_closed_event is NOT set — skipping get_state task start")

    async def ws_disconnected_handler(self) -> None:
        """Handle websocket disconnection."""
        _LOGGER.warning(
            "Websocket connection to HomematicIP Cloud closed (get_state_task_alive=%s)",
            self._get_state_task is not None and not self._get_state_task.done(),
        )
        self._ws_connection_closed.set()
        # Log entity state snapshot at disconnect — for pre/post comparison
        self._log_entity_state_snapshot("pre-reconnect")

    async def ws_reconnected_handler(self, reason: str) -> None:
        """Handle websocket reconnection. Is called when Websocket tries to reconnect."""
        _LOGGER.info(
            "Websocket connection to HomematicIP Cloud trying to reconnect due to reason: %s "
            "(ws_closed_event=%s, get_state_task_alive=%s)",
            reason,
            self._ws_connection_closed.is_set(),
            self._get_state_task is not None and not self._get_state_task.done(),
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
