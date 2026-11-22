"""DataUpdateCoordinator for the Fast.com integration."""

from datetime import timedelta
from typing import override

from fastdotcom import FastDotComError, FastSpeedtestResult, async_fast_com

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_INTERVAL, DOMAIN, LOGGER

type FastdotcomConfigEntry = ConfigEntry[FastdotcomDataUpdateCoordinator]


class FastdotcomDataUpdateCoordinator(
    DataUpdateCoordinator[FastSpeedtestResult | None]
):
    """Class to manage fetching Fast.com data API."""

    def __init__(self, hass: HomeAssistant, entry: FastdotcomConfigEntry) -> None:
        """Initialize the coordinator for Fast.com."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_INTERVAL),
        )

    @override
    async def _async_update_data(self) -> FastSpeedtestResult:
        """Retrieve Fast.com speedtest data asynchronously."""
        session = async_get_clientsession(self.hass)
        try:
            return await async_fast_com(session=session)
        except FastDotComError as exc:
            raise UpdateFailed(f"Error communicating with Fast.com: {exc}") from exc
