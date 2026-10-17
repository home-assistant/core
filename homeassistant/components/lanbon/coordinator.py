"""Fetch authoritative snapshots; WebSocket notifications trigger a full refresh."""

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from aiolanbon import (
    LanbonAuthError,
    LanbonClient,
    LanbonConnectionError,
    LanbonError,
    LanbonEventsUnsupportedError,
    LanbonTimeoutError,
)
from aiolanbon.models import DeviceSnapshot, GatewayInfo

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import LanbonConfigEntry

_LOGGER = logging.getLogger(__name__)
_POLL = timedelta(seconds=15)


class LanbonCoordinator(DataUpdateCoordinator[DeviceSnapshot]):
    """Fetch LOIP device snapshot and optionally listen for events."""

    config_entry: LanbonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LanbonConfigEntry,
        client: LanbonClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=_POLL,
        )
        self.client = client
        self.gateway_verified = False
        self.info: GatewayInfo | None = None
        self._etag: str | None = None
        self._force_snapshot = False
        self._events_task: asyncio.Task | None = None
        self._use_ws = False

    @override
    async def _async_setup(self) -> None:
        """Read gateway info and whether events WebSocket is advertised."""
        try:
            info = await self.client.get_info()
        except LanbonAuthError as err:
            raise ConfigEntryAuthFailed("unauthorized") from err
        except (
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        if not info.api_enabled:
            self.gateway_verified = False
            self.info = None
            self._etag = None
            raise UpdateFailed("Open Integration is disabled")
        self._verify_gateway(info.gateway_id)
        self.info = info
        self._use_ws = bool(info.events_websocket)

    def _verify_gateway(self, gateway_id: str) -> None:
        """Reject data belonging to a different configured gateway."""
        if not gateway_id or gateway_id != self.config_entry.unique_id:
            self.gateway_verified = False
            self.info = None
            self._etag = None
            raise UpdateFailed("Gateway identity does not match the configured gateway")

    @override
    async def _async_update_data(self) -> DeviceSnapshot:
        """GET /devices, using If-None-Match when a revision is already known."""
        try:
            if self.info is None:
                await self._async_setup()
            if self._force_snapshot:
                self._etag = None
                self._force_snapshot = False
            snap = await self.client.get_devices(if_none_match=self._etag)
        except LanbonAuthError as err:
            raise ConfigEntryAuthFailed("unauthorized") from err
        except (
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        if snap is None:
            if self.data is None or not self.gateway_verified:
                raise UpdateFailed("empty snapshot")
            return self.data
        self._verify_gateway(snap.gateway_id)
        self.gateway_verified = True
        self._etag = snap.revision
        return snap

    @override
    async def async_config_entry_first_refresh(self) -> None:
        """Refresh once, then start the events task when the gateway supports it."""
        await super().async_config_entry_first_refresh()
        if self._use_ws:
            self._events_task = self.config_entry.async_create_background_task(
                self.hass, self._events_loop(), name="lanbon-loip-events"
            )

    async def _events_loop(self) -> None:
        try:
            async for _notification in self.client.listen():
                # Revision IDs are opaque; event payloads cannot order HTTP state.
                self._force_snapshot = True
                # Wait for the HTTP response even during debounce cooldown.
                await self.async_refresh()
                if not self.last_update_success:
                    self._use_ws = False
                    return
        except LanbonEventsUnsupportedError:
            _LOGGER.debug("events websocket unsupported; polling /devices")
            self._use_ws = False
        except asyncio.CancelledError:
            raise
        except (
            LanbonAuthError,
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
            OSError,
        ):
            _LOGGER.debug("events loop ended; stay on polling")
            self._use_ws = False

    def async_on_unload(self) -> None:
        """Cancel the events task."""
        if self._events_task and not self._events_task.done():
            self._events_task.cancel()
