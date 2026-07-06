"""Push data-update coordinator for one rtl_433 server (hub config entry).

A thin Home Assistant adapter over :class:`pyrtl_433.Rtl433Client`. The library
owns the transport (the WebSocket connect/reconnect loop, JSON frame parsing,
and event normalization); this coordinator injects Home Assistant's shared
aiohttp session, starts/stops the client with the config-entry lifecycle, and
publishes each normalized event to the entity platform via
:meth:`DataUpdateCoordinator.async_set_updated_data`.

The coordinator holds no polling logic: rtl_433 is ``local_push``. Its
``data`` is the latest :class:`~pyrtl_433.normalizer.NormalizedEvent` per device
key; the sensor platform reads a single measurement field out of it.
"""

import asyncio
from datetime import datetime
import time

from pyrtl_433 import CannotConnect, Rtl433Client
from pyrtl_433.normalizer import NormalizedEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SECURE,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

# How long to wait for the first WebSocket connection before deciding the
# server is unreachable and raising ``ConfigEntryNotReady`` (test-before-setup).
_CONNECT_TIMEOUT = 10.0
_POLL_INTERVAL = 0.25

type Rtl433ConfigEntry = ConfigEntry[Rtl433Coordinator]


class Rtl433Coordinator(DataUpdateCoordinator[dict[str, NormalizedEvent]]):
    """Drive one :class:`pyrtl_433.Rtl433Client` and fan events out to HA."""

    config_entry: Rtl433ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Rtl433ConfigEntry) -> None:
        """Initialize the coordinator and build the transport client."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}-{entry.entry_id}",
        )
        # Last-seen (UTC) per device key, refreshed on every live (non-replay)
        # event; the sensor availability check reads it.
        self.last_seen: dict[str, datetime] = {}
        self._client = Rtl433Client(
            entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            path=entry.data[CONF_PATH],
            secure=entry.data.get(CONF_SECURE, False),
            session=async_get_clientsession(hass),
            on_event=self._handle_event,
        )

    async def _async_setup(self) -> None:
        """Start the client and confirm connectivity (test-before-setup).

        Raises :class:`ConfigEntryNotReady` when the server cannot be reached
        within :data:`_CONNECT_TIMEOUT`, so Home Assistant retries setup later.
        """
        await self._client.start()
        end = time.monotonic() + _CONNECT_TIMEOUT
        while not self._client.connected:
            if time.monotonic() > end:
                await self._client.stop()
                raise ConfigEntryNotReady(
                    f"Cannot connect to rtl_433 server at {self._client.ws_url}"
                )
            await asyncio.sleep(_POLL_INTERVAL)
        # Stop the client only once we own a running one.
        self.config_entry.async_on_unload(self._async_stop)

    async def _async_update_data(self) -> dict[str, NormalizedEvent]:
        """Return the current per-device event map.

        Updates arrive by push (:meth:`_handle_event`), so this only seeds the
        initial (empty) state on the first refresh.
        """
        return self.data or {}

    async def _async_stop(self) -> None:
        """Stop the transport client (never closes the shared HA session)."""
        await self._client.stop()

    @callback
    def _handle_event(self, event: NormalizedEvent) -> None:
        """Publish one normalized event from the client to the entities."""
        key = event.device_key
        if not event.is_replay:
            self.last_seen[key] = dt_util.utcnow()
        data = dict(self.data or {})
        data[key] = event
        self.async_set_updated_data(data)

    @staticmethod
    async def validate_connection(
        hass: HomeAssistant,
        host: str,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_PATH,
        *,
        secure: bool = False,
    ) -> bool:
        """Verify the server is reachable with a short-lived WebSocket connect.

        Returns ``True`` on success; raises :class:`pyrtl_433.CannotConnect` when
        the endpoint cannot be reached. Used by the config flow
        (test-before-configure).
        """
        session = async_get_clientsession(hass)
        return await Rtl433Client.validate_connection(
            session, host, port, path, secure=secure
        )


__all__ = ["CannotConnect", "Rtl433ConfigEntry", "Rtl433Coordinator"]
