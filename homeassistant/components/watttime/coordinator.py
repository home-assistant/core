"""Coordinator for the WattTime integration."""

from datetime import timedelta
from typing import override

from aiowatttime import Client
from aiowatttime.errors import InvalidCredentialsError, WattTimeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BALANCING_AUTHORITY_ABBREV, DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)

type WattTimeData = dict[str, StateType]
type WattTimeConfigEntry = ConfigEntry[WattTimeCoordinator]


class WattTimeCoordinator(DataUpdateCoordinator[WattTimeData]):
    """Coordinator for WattTime data updates."""

    config_entry: WattTimeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WattTimeConfigEntry,
        client: Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> WattTimeData:
        """Get the latest realtime emissions data."""
        try:
            data = await self.client.emissions.async_get_realtime_emissions(
                self.config_entry.data[CONF_BALANCING_AUTHORITY_ABBREV]
            )
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed("Invalid username/password") from err
        except WattTimeError as err:
            raise UpdateFailed(
                f"Error while requesting data from WattTime: {err}"
            ) from err

        return {"percent": data["data"][0]["value"]}
