"""Data update coordinator for NexBlue."""

from collections.abc import Callable
from datetime import datetime
from typing import override

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueConnectionError,
    NexBlueDeviceOfflineError,
    NexBlueError,
    NexBlueRateLimitError,
)
from nexblue_api.models import ChargerStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, LOGGER, UPDATE_INTERVAL

type NexBlueConfigEntry = ConfigEntry[NexBlueDataUpdateCoordinator]

INITIAL_COMMAND_REFRESH_DELAY = 3
FINAL_COMMAND_REFRESH_DELAY = 20
COMMAND_REFRESH_DELAYS = (
    INITIAL_COMMAND_REFRESH_DELAY,
    FINAL_COMMAND_REFRESH_DELAY,
)


class NexBlueDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, ChargerStatus | None]]
):
    """Fetch all charger telemetry in a coordinated update."""

    config_entry: NexBlueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NexBlueConfigEntry,
        client: NexBlueClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._pending_command_refreshes: dict[str, set[Callable[[], None]]] = {}
        entry.async_on_unload(self.async_cancel_pending_command_refreshes)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"NexBlue {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )

    @callback
    def async_schedule_command_refreshes(self, serial_number: str) -> None:
        """Schedule shared follow-up refreshes after a charger command."""
        self.async_cancel_pending_command_refreshes(serial_number)
        pending_refreshes: set[Callable[[], None]] = set()
        self._pending_command_refreshes[serial_number] = pending_refreshes

        def _schedule_refresh(delay: int) -> None:
            cancel: Callable[[], None] | None = None

            @callback
            def _request_refresh(_now: datetime) -> None:
                """Request coordinator data after a charger command."""
                if cancel is not None:
                    pending_refreshes.discard(cancel)
                if not pending_refreshes:
                    self._pending_command_refreshes.pop(serial_number, None)
                self.config_entry.async_create_task(
                    self.hass,
                    self.async_request_refresh(),
                    name="NexBlue command refresh",
                )

            cancel = async_call_later(self.hass, delay, _request_refresh)
            pending_refreshes.add(cancel)

        for delay in COMMAND_REFRESH_DELAYS:
            _schedule_refresh(delay)

    @callback
    def async_cancel_pending_command_refreshes(
        self, serial_number: str | None = None
    ) -> None:
        """Cancel pending command refreshes for a charger or the whole entry."""
        if serial_number is None:
            pending_refreshes = [
                cancel
                for refreshes in self._pending_command_refreshes.values()
                for cancel in refreshes
            ]
            self._pending_command_refreshes.clear()
        else:
            pending_refreshes = list(
                self._pending_command_refreshes.pop(serial_number, set())
            )

        for cancel in pending_refreshes:
            cancel()

    @override
    async def _async_update_data(self) -> dict[str, ChargerStatus | None]:
        """Fetch status for every charger visible to the configured account."""
        try:
            await self._async_ensure_authorized()
            chargers = await self.client.async_list_chargers()
            data: dict[str, ChargerStatus | None] = {}
            for charger in chargers:
                try:
                    data[
                        charger.serial_number
                    ] = await self.client.async_get_charger_status(
                        charger.serial_number
                    )
                except NexBlueAuthError, NexBlueConnectionError, NexBlueRateLimitError:
                    raise
                except NexBlueDeviceOfflineError, NexBlueError:
                    data[charger.serial_number] = None
        except NexBlueAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (NexBlueConnectionError, NexBlueRateLimitError, NexBlueError) as err:
            raise UpdateFailed("Unable to update NexBlue charger data") from err

        return data

    async def _async_ensure_authorized(self) -> None:
        """Refresh the access token, falling back to one saved-password login."""
        try:
            token = await self.client.async_ensure_access_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
        except NexBlueAuthError:
            token = await self.client.async_login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
            if not token.refresh_token:
                raise NexBlueAuthError from None

        if (
            token
            and token.refresh_token
            and token.refresh_token != self.config_entry.data[CONF_REFRESH_TOKEN]
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_REFRESH_TOKEN: token.refresh_token,
                },
            )
