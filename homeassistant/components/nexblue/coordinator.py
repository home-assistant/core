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

type NexBlueConfigEntry = ConfigEntry["NexBlueDataUpdateCoordinator"]

COMMAND_REFRESH_DELAYS = (3, 20)


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
        self._pending_command_refreshes: set[Callable[[], None]] = set()
        entry.async_on_unload(self.async_cancel_pending_command_refreshes)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"NexBlue {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )

    @callback
    def async_schedule_command_refreshes(self) -> None:
        """Schedule shared follow-up refreshes after a charger command."""
        self.async_cancel_pending_command_refreshes()

        def _schedule_refresh(delay: int) -> None:
            cancel: Callable[[], None] | None = None

            @callback
            def _request_refresh(_now: datetime) -> None:
                """Request coordinator data after a charger command."""
                if cancel is not None:
                    self._pending_command_refreshes.discard(cancel)
                self.config_entry.async_create_task(
                    self.hass,
                    self.async_request_refresh(),
                    name="NexBlue command refresh",
                )

            cancel = async_call_later(self.hass, delay, _request_refresh)
            self._pending_command_refreshes.add(cancel)

        for delay in COMMAND_REFRESH_DELAYS:
            _schedule_refresh(delay)

    @callback
    def async_cancel_pending_command_refreshes(self) -> None:
        """Cancel command refreshes that have not fired."""
        for cancel in self._pending_command_refreshes:
            cancel()
        self._pending_command_refreshes.clear()

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
