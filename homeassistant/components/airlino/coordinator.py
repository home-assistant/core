"""DataUpdateCoordinator for AirLino."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from airlino_api import AirlinoApi, AirlinoApiConnectionError, AirlinoApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

type AirlinoConfigEntry = ConfigEntry[AirlinoDataUpdateCoordinator]


@dataclass
class AirlinoData:
    """Data polled from an AirLino device."""

    player: dict[str, Any]
    volume: int


class AirlinoDataUpdateCoordinator(TimestampDataUpdateCoordinator[AirlinoData]):
    """Coordinate AirLino updates."""

    config_entry: AirlinoConfigEntry
    device_info: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirlinoConfigEntry,
        api: AirlinoApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="AirLino",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_request[T](self, request: Callable[[], Awaitable[T]]) -> T:
        """Run an API request and raise UpdateFailed on errors."""
        try:
            return await request()
        except AirlinoApiConnectionError as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except AirlinoApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err

    @override
    async def _async_setup(self) -> None:
        """Fetch the static device information."""
        self.device_info = await self._async_request(self.api.async_get_device_info)

    @override
    async def _async_update_data(self) -> AirlinoData:
        """Fetch the playback status and volume."""
        player = await self._async_request(self.api.async_get_player_status)
        volume = await self._async_request(self.api.async_get_master_volume)
        return AirlinoData(player=player, volume=volume)
