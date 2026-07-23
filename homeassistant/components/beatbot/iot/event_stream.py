"""WebSocket event stream for incremental Beatbot cloud state updates."""

import asyncio
from collections import OrderedDict
from contextlib import suppress
import logging
import random

from aiohttp import ClientError
from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotConnectionError,
    BeatbotConnectionReplacedError,
    BeatbotEvent,
    BeatbotEventStream,
    BeatbotTokenRejectedError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..api import BeatbotAPI
from ..coordinator import BeatbotCoordinator
from .const import (
    DOMAIN,
    EVENT_DEDUP_CACHE_SIZE,
    EVENT_HEARTBEAT_INTERVAL,
    EVENT_HEARTBEAT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

_RECONNECT_DELAYS = (1.0, 2.0, 4.0, 8.0, 30.0, 60.0)
_RECONNECT_JITTER = 0.2


_ConnectionReplaced = BeatbotConnectionReplacedError
_RefreshToken = BeatbotTokenRejectedError


class BeatbotEventClient:
    """Maintain the account-scoped cloud event WebSocket."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        api: BeatbotAPI,
        coordinator: BeatbotCoordinator,
    ) -> None:
        """Initialize the Beatbot event client."""
        self._hass = hass
        self._entry = entry
        self._oauth_session = oauth_session
        self._api = api
        self._coordinator = coordinator
        self._task: asyncio.Task[None] | None = None
        self._stream: BeatbotEventStream | None = None
        self._stopping = False
        self._token_refresh_attempted = False
        self._has_connected = False
        self._connection_generation = 0
        self._seen_event_ids: OrderedDict[str, None] = OrderedDict()
        self._reload_scheduled = False

    def async_start(self) -> None:
        """Start the connection supervisor without blocking setup."""
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = self._entry.async_create_background_task(
                self._hass,
                self._run(),
                f"beatbot_event_stream_{self._entry.entry_id}",
            )

    async def async_stop(self) -> None:
        """Stop and close the stream. Safe to call repeatedly."""
        self._stopping = True
        if self._stream is not None:
            await self._stream.close()
        task, self._task = self._task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        failures = 0
        try:
            while not self._stopping:
                try:
                    connection_generation = self._connection_generation
                    await self._connect_and_receive()
                except asyncio.CancelledError:
                    raise
                except _ConnectionReplaced:
                    # 4002 is terminal. Reconnecting would make multiple HA
                    # instances continuously evict one another.
                    return
                except _RefreshToken as err:
                    if self._token_refresh_attempted:
                        raise ConfigEntryAuthFailed(
                            translation_domain=DOMAIN,
                            translation_key="auth_error",
                        ) from err
                    await self._async_refresh_token_once(err.access_token)
                    self._token_refresh_attempted = True
                    failures = 0
                    continue
                except BeatbotAuthenticationError, ConfigEntryAuthFailed:
                    _LOGGER.warning(
                        "Beatbot event stream authorization failed; "
                        "starting reauthentication"
                    )
                    self._entry.async_start_reauth(self._hass)
                    return
                except (
                    TimeoutError,
                    BeatbotConnectionError,
                    ClientError,
                    ConnectionError,
                ) as err:
                    if self._connection_generation != connection_generation:
                        failures = 0
                    failures += 1
                    _LOGGER.warning("Beatbot event stream disconnected: %s", err)
                except Exception:
                    failures += 1
                    _LOGGER.exception("Unexpected Beatbot event stream failure")

                if self._stopping:
                    return
                delay = _RECONNECT_DELAYS[min(failures - 1, len(_RECONNECT_DELAYS) - 1)]
                delay *= random.uniform(
                    1.0 - _RECONNECT_JITTER, 1.0 + _RECONNECT_JITTER
                )
                await asyncio.sleep(delay)
        except ConfigEntryAuthFailed:
            _LOGGER.warning("Beatbot token refresh failed; starting reauthentication")
            self._entry.async_start_reauth(self._hass)
        finally:
            await self._async_close_connection()

    async def _async_refresh_token_once(self, rejected_access_token: str) -> None:
        """Refresh a rejected token through the session's shared rotation lock."""
        current_token = self._oauth_session.token
        if current_token.get("access_token") != rejected_access_token:
            _LOGGER.debug(
                "Skipping Beatbot OAuth refresh for an already replaced token "
                "(entry_id=%s)",
                self._entry.entry_id,
            )
            return
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                "token": {**current_token, "expires_at": 0},
            },
        )
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.warning(
                "Transient Beatbot OAuth refresh failure after event stream rejection "
                "(entry_id=%s): %s",
                self._entry.entry_id,
                err,
            )
            raise BeatbotConnectionError("OAuth token refresh failed") from err
        _LOGGER.debug(
            "Beatbot OAuth token rotated after event stream rejection (entry_id=%s)",
            self._entry.entry_id,
        )

    async def _connect_and_receive(self) -> None:
        await self._oauth_session.async_ensure_token_valid()
        token = self._oauth_session.token.get("access_token")
        if not token:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            )

        stream = BeatbotEventStream(
            async_get_clientsession(self._hass),
            self._api.event_stream_url,
            token,
            heartbeat=EVENT_HEARTBEAT_INTERVAL,
            receive_timeout=EVENT_HEARTBEAT_TIMEOUT,
        )
        self._stream = stream
        try:
            await stream.connect()
            is_reconnect = self._has_connected
            self._has_connected = True
            self._connection_generation += 1
            _LOGGER.debug(
                "Connected to Beatbot event stream at %s", self._api.event_stream_url
            )
            if is_reconnect:
                await self._coordinator.async_request_refresh()
            while not self._stopping:
                try:
                    event = await stream.receive()
                except BeatbotConnectionError as err:
                    if str(err).startswith("Event "):
                        _LOGGER.warning("Ignoring malformed Beatbot event: %s", err)
                        continue
                    raise
                self._token_refresh_attempted = False
                self._handle_event(event)
        finally:
            await stream.close()
            if self._stream is stream:
                self._stream = None

    async def _async_close_connection(self) -> None:
        """Close and discard the current connection."""
        stream, self._stream = self._stream, None
        if stream is not None:
            await stream.close()

    def _handle_text_message(self, raw: str) -> None:
        """Parse and dispatch one text event."""
        try:
            self._handle_event(BeatbotEventStream.parse_event(raw))
        except BeatbotConnectionError as err:
            _LOGGER.warning("Ignoring malformed Beatbot event: %s", err)

    def _handle_event(self, event: BeatbotEvent) -> None:
        """Apply one validated event to Home Assistant state."""
        event_id = event.event_id
        event_type = event.event_type
        device_id = event.device_id
        payload = event.payload
        if event_id in self._seen_event_ids:
            return
        self._remember_event(event_id)
        _LOGGER.debug(
            "Received Beatbot event eventId=%s deviceId=%s type=%s",
            event_id,
            device_id,
            event_type,
        )

        if event_type == "properties_changed":
            if not isinstance(payload, dict) or not isinstance(
                interface_info := payload.get("interfaceInfo"), str
            ):
                _LOGGER.warning("Ignoring malformed Beatbot property event")
                return
            self._coordinator.async_apply_device_event(
                device_id, {interface_info: payload.get("value")}
            )
        elif event_type == "status":
            if not isinstance(payload, dict) or not isinstance(
                online := payload.get("online"), bool
            ):
                _LOGGER.warning("Ignoring malformed Beatbot status event")
                return
            self._coordinator.async_apply_device_event(
                device_id, None, is_online=online
            )
        elif event_type == "device_added":
            if not isinstance(payload, dict) or payload.get("deviceId") != device_id:
                _LOGGER.warning("Ignoring malformed Beatbot device-added event")
                return
            self._schedule_entry_reload()
        elif event_type == "device_removed":
            self._remove_device_from_registries(device_id)
            self._schedule_entry_reload()
        else:
            _LOGGER.debug("Ignoring unknown Beatbot event type %s", event_type)

    def _schedule_entry_reload(self) -> None:
        """Reload all platforms after the account's device set changes."""
        if self._reload_scheduled or self._stopping:
            return
        self._reload_scheduled = True

        async def _reload() -> None:
            try:
                await self._hass.config_entries.async_reload(self._entry.entry_id)
            finally:
                self._reload_scheduled = False

        self._hass.async_create_task(
            _reload(), f"beatbot_reload_{self._entry.entry_id}"
        )

    def _remove_device_from_registries(self, device_id: str) -> None:
        """Remove entities and the device registry entry after account removal."""
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
        if device is None:
            return

        entity_registry = er.async_get(self._hass)
        for entity in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            if entity.config_entry_id == self._entry.entry_id:
                entity_registry.async_remove(entity.entity_id)
        device_registry.async_update_device(
            device.id, remove_config_entry_id=self._entry.entry_id
        )

    def _remember_event(self, event_id: str) -> None:
        self._seen_event_ids[event_id] = None
        self._seen_event_ids.move_to_end(event_id)
        while len(self._seen_event_ids) > EVENT_DEDUP_CACHE_SIZE:
            self._seen_event_ids.popitem(last=False)
