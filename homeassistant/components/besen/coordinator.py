"""Coordinator for Besen push updates."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, override

from besen.client import BesenClient
from besen.exceptions import CannotConnect, CommandFailed
from besen.models import BesenData

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .lan import async_release_udp_hub

if TYPE_CHECKING:
    from . import BesenConfigEntry

_LOGGER = logging.getLogger(__name__)


class BesenCoordinator(DataUpdateCoordinator[BesenData]):
    """Coordinate Besen state updates."""

    config_entry: BesenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BesenConfigEntry,
        client: BesenClient,
        *,
        uses_lan: bool = False,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.client = client
        self._remove_listener: Callable[[], None] | None = None
        self._client_stopped = True
        self._connection_lock = asyncio.Lock()
        self._uses_lan = uses_lan

    async def async_start(self) -> None:
        """Start listening to charger updates."""

        self._remove_listener = self.client.add_listener(self._handle_client_update)
        self._client_stopped = False
        try:
            await self.client.async_start()
        except Exception:
            if self._remove_listener is not None:
                self._remove_listener()
                self._remove_listener = None
            with suppress(Exception):
                await self._async_stop_client()
            await self._async_release_listener()
            raise
        self.async_set_updated_data(self.client.state)

    @override
    async def async_shutdown(self) -> None:
        """Stop listening to charger updates."""

        await super().async_shutdown()
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        async with self._connection_lock:
            try:
                await self._async_stop_client()
            finally:
                await self._async_release_listener()

    async def async_pause_connection(self) -> None:
        """Release the current client before validating another connection."""
        async with self._connection_lock:
            if self._shutdown_requested:
                raise CannotConnect("Charger entry is unloading")
            await self._async_stop_client()
            if self.client.is_connected:
                raise CannotConnect("Previous connection was not released")

    async def async_resume_connection(self) -> None:
        """Restore the saved connection only while this coordinator is active."""
        async with self._connection_lock:
            if self._shutdown_requested:
                return
            self._client_stopped = False
            await self.client.async_start()

    async def _async_release_listener(self) -> None:
        """Release this entry's listener exactly once."""
        if self._uses_lan:
            self._uses_lan = False
            await async_release_udp_hub(self.hass)

    @override
    async def _async_update_data(self) -> BesenData:
        """Return latest push state for manual refresh requests."""

        return self.client.state

    @callback
    def _handle_client_update(self, data: BesenData) -> None:
        """Publish a client state update."""

        self.async_set_updated_data(data)
        assert self.config_entry is not None
        if data.auth_failed and self.config_entry.state is ConfigEntryState.LOADED:
            # Setup failures are handled by ConfigEntryAuthFailed in __init__.py.
            self.config_entry.async_start_reauth(self.hass)

    async def async_start_charging(
        self, start: datetime | None = None, duration: timedelta | None = None
    ) -> None:
        """Start charging, optionally at a later time or for a limited time."""

        command = self.client.async_start_charging(
            start=None if start is None else dt_util.as_utc(start),
            duration_minutes=(
                None if duration is None else int(duration.total_seconds() // 60)
            ),
        )
        try:
            await self._async_run_command(command)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_start",
            ) from err

    async def async_stop_charging(self) -> None:
        """Stop charging."""

        await self._async_run_command(self.client.async_stop_charging())

    async def async_set_charge_amps(self, amps: int) -> None:
        """Set the charging current."""

        await self._async_run_command(self.client.async_set_charge_amps(amps))

    async def async_set_temperature_unit(self, unit: str) -> None:
        """Set the charger display temperature unit."""

        await self._async_run_command(self.client.async_set_temperature_unit(unit))

    async def _async_run_command(self, command: Awaitable[None]) -> None:
        """Run a charger command and translate command failures."""

        try:
            await command
        except CommandFailed as err:
            self.async_set_updated_data(self.client.state)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err

    async def _async_stop_client(self) -> None:
        """Stop the client if it is still running."""

        if self._client_stopped:
            return
        await self.client.async_stop()
        self._client_stopped = True
