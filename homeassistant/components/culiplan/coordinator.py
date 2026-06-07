"""DataUpdateCoordinator for the Culiplan integration.

The coordinator runs REST polling on a 5-minute interval and, in
parallel, maintains a Socket.IO connection to ``/ha-events`` for push
updates. If the push connection drops we keep working off the REST
poll until it reconnects.
"""

import asyncio
import contextlib
from datetime import timedelta
import logging
import random
from typing import Any, cast

import socketio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CuliplanApiClient, CuliplanApiError
from .const import BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

HA_NAMESPACE = "/ha-events"
HA_EVENT = "ha:event"
HA_ERROR = "ha:error"

# Culiplan plans rarely change minute-by-minute; the Socket.IO push channel
# delivers near-real-time updates when connected. 5 minutes is the safety-net
# poll interval used only when push is disconnected (Bronze: appropriate-polling).
_DEFAULT_POLL_INTERVAL = timedelta(minutes=5)
_RECONNECT_INITIAL_DELAY = 2.0
# Cap reconnect backoff at 60s so a recovered backend is rediscovered quickly
# without hammering it during a full outage.
_RECONNECT_MAX_DELAY = 60.0
_RECONNECT_FACTOR = 2.0
# Random jitter (0-25 % of the current delay) prevents N coordinators from
# reconnecting in lockstep after a shared backend outage. `random` (not
# `secrets`) is fine here - this is anti-thundering-herd, not a crypto seed.
_RECONNECT_JITTER_FRACTION = 0.25
# Socket.IO initial-handshake timeout. Longer than the REST timeout because
# the WS upgrade has to traverse the same path plus an Engine.IO handshake.
_SOCKETIO_HANDSHAKE_TIMEOUT = 15


class CuliplanCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Push-first coordinator with REST polling fallback."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: CuliplanApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialise the coordinator and remember our config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=_DEFAULT_POLL_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self._sio: socketio.AsyncClient | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._connected = False
        self._stopped = False

    @property
    def push_connected(self) -> bool:
        """Return ``True`` while the Socket.IO push channel is connected."""
        return self._connected

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def async_start(self) -> None:
        """Connect the Socket.IO push channel."""
        self._stopped = False
        await self._connect()

    async def async_stop(self) -> None:
        """Disconnect Socket.IO and cancel any reconnect task."""
        self._stopped = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None
        if self._sio is not None:
            with contextlib.suppress(socketio.exceptions.SocketIOError, OSError):
                await self._sio.disconnect()
            self._sio = None

    # ─── DataUpdateCoordinator protocol ──────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch a full snapshot from REST.

        Core endpoints (meal plans, shopping list) failing aborts the
        update so HA marks entities unavailable. The pantry slice is
        best-effort because that scope is opt-in for users on a free
        plan and failing it shouldn't break the rest.
        """
        try:
            await self._refresh_token()
            meal_plans = await self.client.async_get_meal_plans()
            shopping_lists = await self.client.async_get_shopping_lists()
        except ConfigEntryAuthFailed:
            raise
        except CuliplanApiError as err:
            raise UpdateFailed(f"Culiplan REST fetch failed: {err}") from err

        pantry_items: list[dict[str, Any]] = []
        try:
            pantry_items = await self.client.async_get_pantry_items()
        except CuliplanApiError as err:
            _LOGGER.debug("Pantry fetch failed (continuing): %s", err)

        return {
            "meal_plans": meal_plans,
            "shopping_lists": shopping_lists,
            "pantry_items": pantry_items,
        }

    # ─── Socket.IO connection ─────────────────────────────────────────────────

    async def _connect(self) -> None:
        """Open the Socket.IO connection to ``/ha-events``."""
        if self._stopped:
            return

        access_token = await self._refresh_token()

        sio = socketio.AsyncClient(
            reconnection=False,
            logger=False,
            engineio_logger=False,
        )
        self._sio = sio

        @sio.event(namespace=HA_NAMESPACE)  # type: ignore[untyped-decorator]
        async def connect() -> None:
            _LOGGER.debug("Connected to Culiplan /ha-events")
            self._connected = True
            await self.async_request_refresh()

        @sio.event(namespace=HA_NAMESPACE)  # type: ignore[untyped-decorator]
        async def disconnect(reason: str | None = None) -> None:
            _LOGGER.debug("Disconnected from Culiplan /ha-events: %s", reason)
            self._connected = False
            self._schedule_reconnect()

        @sio.on(HA_EVENT, namespace=HA_NAMESPACE)  # type: ignore[untyped-decorator]
        async def on_ha_event(payload: dict[str, Any]) -> None:
            await self._handle_event(payload)

        @sio.on(HA_ERROR, namespace=HA_NAMESPACE)  # type: ignore[untyped-decorator]
        async def on_ha_error(payload: dict[str, Any]) -> None:
            _LOGGER.debug("HA gateway error: %s", payload.get("message"))

        try:
            await sio.connect(
                BASE_URL,
                namespaces=[HA_NAMESPACE],
                auth={"token": access_token},
                transports=["websocket"],
                wait_timeout=_SOCKETIO_HANDSHAKE_TIMEOUT,
            )
        except socketio.exceptions.ConnectionError as err:
            _LOGGER.debug("Failed to connect to /ha-events: %s", err)
            self._connected = False
            self._schedule_reconnect()

    async def _handle_event(self, payload: dict[str, Any]) -> None:
        event_type: str = payload.get("type", "")
        _LOGGER.debug("ha:event type=%s", event_type)
        if event_type == "meal_plan.updated":
            await self._refresh_meal_plans()
        elif event_type.startswith("shopping_list.item."):
            await self._refresh_shopping_lists()
        elif event_type.startswith("pantry.item."):
            await self._refresh_pantry()

    async def _refresh_meal_plans(self) -> None:
        try:
            meal_plans = await self.client.async_get_meal_plans()
        except CuliplanApiError as err:
            _LOGGER.debug("Failed to refresh meal plans: %s", err)
            return
        self.async_set_updated_data({**(self.data or {}), "meal_plans": meal_plans})

    async def _refresh_shopping_lists(self) -> None:
        try:
            shopping_lists = await self.client.async_get_shopping_lists()
        except CuliplanApiError as err:
            _LOGGER.debug("Failed to refresh shopping lists: %s", err)
            return
        self.async_set_updated_data(
            {**(self.data or {}), "shopping_lists": shopping_lists}
        )

    async def _refresh_pantry(self) -> None:
        try:
            pantry_items = await self.client.async_get_pantry_items()
        except CuliplanApiError as err:
            _LOGGER.debug("Failed to refresh pantry items: %s", err)
            return
        self.async_set_updated_data({**(self.data or {}), "pantry_items": pantry_items})

    # ─── Reconnect logic ─────────────────────────────────────────────────────

    def _schedule_reconnect(self, delay: float = _RECONNECT_INITIAL_DELAY) -> None:
        if self._stopped:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return

        async def _reconnect_loop(initial_delay: float) -> None:
            base = initial_delay
            while not self._connected and not self._stopped:
                # Apply jitter on each attempt so two coordinators sharing the
                # same outage clock don't pick the same delay.
                jitter = random.uniform(0, base * _RECONNECT_JITTER_FRACTION)
                wait = base + jitter
                _LOGGER.debug("Reconnecting to Culiplan in %.1fs", wait)
                await asyncio.sleep(wait)
                if self._stopped:
                    return
                try:
                    if self._sio is not None:
                        await self._sio.disconnect()
                    await self._connect()
                    if self._connected:
                        return
                except (socketio.exceptions.SocketIOError, OSError) as err:
                    _LOGGER.debug("Reconnect attempt failed: %s", err)
                base = min(base * _RECONNECT_FACTOR, _RECONNECT_MAX_DELAY)

        self._reconnect_task = self.hass.async_create_background_task(
            _reconnect_loop(delay),
            name=f"{DOMAIN}_reconnect",
        )

    # ─── Token helpers ───────────────────────────────────────────────────────

    async def _refresh_token(self) -> str:
        """Ensure the OAuth token is valid and propagate it to the API client."""
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                self.hass, self.config_entry
            )
        )
        session = config_entry_oauth2_flow.OAuth2Session(
            self.hass, self.config_entry, implementation
        )
        await session.async_ensure_token_valid()
        token = cast(str, session.token.get("access_token", ""))
        self.client.set_access_token(token)
        return token
