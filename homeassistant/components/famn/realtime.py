"""Push updates from the Famn realtime gateway over WebSocket."""

import asyncio
import random
from typing import Any

import aiohttp
from famn_sdk import ApiError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import BASE_URL, EVENT_FAMN_EVENT, LOGGER
from .coordinator import FamnConfigEntry

WS_URL = BASE_URL.replace("http", "ws", 1) + "/realtime/ws"

# The gateway confirms the Redis subscription before acknowledging, so a
# slow acknowledgement means something is genuinely wrong.
AUTH_TIMEOUT = 10

# aiohttp sends a ping at this interval and drops the connection when the
# pong stays out, catching half-open sockets. The gateway pings every 30
# seconds and disconnects after 90 seconds of silence.
HEARTBEAT = 30.0

RECONNECT_MIN_DELAY = 5.0
RECONNECT_MAX_DELAY = 300.0
RECONNECT_MAX_DOUBLINGS = 6


class FamnRealtime:
    """Feed gateway events into the data coordinators.

    The gateway authenticates the paired device's access token and then
    streams the space's events; polling stays on as a fallback, this only
    makes updates immediate. Access tokens live about ten minutes — a fresh
    auth frame on the open socket extends the session, so the connection
    survives token rotation without reconnecting.
    """

    def __init__(self, hass: HomeAssistant, entry: FamnConfigEntry) -> None:
        """Initialize the realtime client."""
        self.hass = hass
        self.entry = entry
        self.auth = entry.runtime_data.chores.auth
        self._session = async_get_clientsession(hass)
        # Which coordinator each gateway topic feeds. Topics on the space
        # channel that have no entities here (lists, chats, ...) are simply
        # not in the map.
        self._topic_coordinators: dict[str, DataUpdateCoordinator[Any]] = {
            "TaskList": entry.runtime_data.chores,
            "TaskItem": entry.runtime_data.chores,
            "Calendar": entry.runtime_data.calendars,
            "SpaceScore": entry.runtime_data.scores,
            "List": entry.runtime_data.shopping,
            "ListItem": entry.runtime_data.shopping,
            "MealSlot": entry.runtime_data.meals,
        }

    async def async_run(self) -> None:
        """Keep a gateway connection alive until the entry is unloaded.

        Runs as a config-entry background task, so cancellation is the
        shutdown signal.
        """
        failures = 0
        while True:
            try:
                connected = await self._async_connect_once()
            except ConfigEntryAuthFailed:
                # The device registration is gone; reconnecting cannot fix
                # that, only pairing again can.
                self.entry.async_start_reauth(self.hass)
                return
            except (ApiError, aiohttp.ClientError, TimeoutError) as err:
                # ApiError comes from a failed token rotation; transient
                # rotation errors reconnect just like transport errors.
                connected = False
                LOGGER.debug("Famn realtime connection failed: %s", err)

            failures = 0 if connected else failures + 1
            delay = min(
                RECONNECT_MIN_DELAY * 2 ** min(failures, RECONNECT_MAX_DOUBLINGS),
                RECONNECT_MAX_DELAY,
            ) * random.uniform(0.8, 1.2)
            await asyncio.sleep(delay)

    async def _async_connect_once(self) -> bool:
        """Connect, authenticate, and forward events until the socket closes.

        Returns whether a session was established, so the caller resets its
        backoff only for connections that actually worked.
        """
        token = await self.auth.async_get_access_token()

        async with self._session.ws_connect(WS_URL, heartbeat=HEARTBEAT) as ws:
            await ws.send_json({"type": "auth", "token": token})

            async with asyncio.timeout(AUTH_TIMEOUT):
                if not await self._async_await_auth_ok(ws):
                    return False

            LOGGER.debug("Connected to the Famn realtime gateway")
            # auth_ok means the subscription is live; one refresh now closes
            # the gap of anything that changed while disconnected.
            for coordinator in dict.fromkeys(self._topic_coordinators.values()):
                await coordinator.async_request_refresh()

            return await self._async_read_events(ws)

    async def _async_await_auth_ok(self, ws: aiohttp.ClientWebSocketResponse) -> bool:
        """Wait for the gateway to acknowledge the auth frame."""
        msg = await ws.receive()
        if msg.type is not aiohttp.WSMsgType.TEXT:
            return False

        data: dict[str, Any] = msg.json()
        if data.get("type") == "auth_ok":
            return True

        LOGGER.debug("Famn realtime gateway rejected the session: %s", data)
        # The gateway found the token invalid even though its expiry looked
        # fine locally (revoked device, clock skew). Rotating it on the next
        # attempt either fixes the mismatch or surfaces the revocation as
        # ConfigEntryAuthFailed instead of retrying into the same wall.
        self.auth.invalidate()
        return False

    async def _async_read_events(self, ws: aiohttp.ClientWebSocketResponse) -> bool:
        """Forward gateway events until the connection ends.

        Instead of a second timer task, the receive timeout doubles as the
        token-renewal schedule: whenever the renewal deadline passes, a
        fresh auth frame extends the session in place.

        Returns whether the session was healthy while it lasted.
        """
        renewed = False
        while True:
            remaining = (self.auth.reauth_at - dt_util.utcnow()).total_seconds()
            if remaining <= 0:
                if renewed:
                    # The token that was just rotated is already due for
                    # renewal again, so the expiry is not advancing — a
                    # server clock ahead of ours, or an expiry echoed back
                    # unchanged. Renewing once more would spin against the
                    # gateway at full speed, so drop the socket and let the
                    # reconnect backoff slow the retries down.
                    LOGGER.debug(
                        "Famn returned an access token that is already due for "
                        "renewal; dropping the realtime session"
                    )
                    return False
                token = await self.auth.async_get_access_token()
                await ws.send_json({"type": "auth", "token": token})
                renewed = True
                continue
            renewed = False

            try:
                async with asyncio.timeout(remaining):
                    msg = await ws.receive()
            except TimeoutError:
                # Renewal deadline reached; loop back to send a fresh token.
                continue

            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                return True
            if msg.type is not aiohttp.WSMsgType.TEXT:
                continue

            data: dict[str, Any] = msg.json()
            match data.get("type"):
                case "event":
                    # Every event goes on the bus — automations react to any
                    # family activity, entities or not.
                    self.hass.bus.async_fire(
                        EVENT_FAMN_EVENT,
                        {
                            "topic": data.get("topic"),
                            "action": data.get("action"),
                            "space_id": data.get("spaceId"),
                            "event_id": data.get("eventId"),
                            "payload": data.get("payload"),
                        },
                    )
                    if coordinator := self._topic_coordinators.get(
                        data.get("topic", "")
                    ):
                        await coordinator.async_request_refresh()
                case "error":
                    LOGGER.debug("Famn realtime gateway error: %s", data)
                    if data.get("code") in (401, 403):
                        # The session is dead; reconnect with a fresh token.
                        self.auth.invalidate()
                        return True
                case _:
                    # auth_ok for renewals, pong, and any future frame types.
                    pass
