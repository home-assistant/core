"""Data update coordinator for NexBlue."""

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, LOGGER, UPDATE_INTERVAL

type NexBlueConfigEntry = ConfigEntry["NexBlueDataUpdateCoordinator"]


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
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"NexBlue {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )

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
