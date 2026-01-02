"""The coordinator for Hypontech Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hyponcloud import ConnectionError as HyponConnectionError, HyponCloud, OverviewData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class HypontechData:
    """Store runtime data."""

    coordinator: HypontechDataCoordinator


type HypontechConfigEntry = ConfigEntry[HypontechData]


class HypontechDataCoordinator(DataUpdateCoordinator[OverviewData]):
    """Coordinator used for all sensors."""

    config_entry: HypontechConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HypontechConfigEntry,
        api: HyponCloud,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Hypontech Data",
            update_interval=timedelta(seconds=60),
        )
        self.api = api

    async def _async_update_data(self) -> OverviewData:
        try:
            data = await self.api.get_overview()
        except HyponConnectionError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from ex
        return data
