"""Coordinator for Besen BS20 push updates."""

from collections.abc import Awaitable, Callable
from contextlib import suppress
import logging
from typing import override

from besen_bs20.client import BesenBS20Client
from besen_bs20.exceptions import CommandFailed
from besen_bs20.models import BesenBS20Data

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BesenBS20Coordinator(DataUpdateCoordinator[BesenBS20Data]):
    """Coordinate Besen BS20 state updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BesenBS20Client,
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

    async def async_start(self) -> None:
        """Start listening to charger updates."""

        self._remove_listener = self.client.add_listener(self._handle_client_update)
        try:
            await self.client.async_start()
        except Exception:
            if self._remove_listener is not None:
                self._remove_listener()
                self._remove_listener = None
            with suppress(Exception):
                await self.client.async_stop()
            raise
        self.async_set_updated_data(self.client.state)

    @override
    async def async_shutdown(self) -> None:
        """Stop listening to charger updates."""

        await super().async_shutdown()
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await self.client.async_stop()

    @override
    async def _async_update_data(self) -> BesenBS20Data:
        """Return latest push state for manual refresh requests."""

        return self.client.state

    @callback
    def _handle_client_update(self, data: BesenBS20Data) -> None:
        """Publish a client state update."""

        self.async_set_updated_data(data)

    async def async_start_charging(self) -> None:
        """Start charging."""

        await self._async_run_command(self.client.async_start_charging())

    async def async_stop_charging(self) -> None:
        """Stop charging."""

        await self._async_run_command(self.client.async_stop_charging())

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
