"""Data update coordinator for Twente Milieu."""

from __future__ import annotations

from datetime import date

from twentemilieu import (
    TwenteMilieu,
    TwenteMilieuConnectionError,
    TwenteMilieuError,
    WasteType,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
)

type TwenteMilieuConfigEntry = ConfigEntry[TwenteMilieuDataUpdateCoordinator]


class TwenteMilieuDataUpdateCoordinator(
    DataUpdateCoordinator[dict[WasteType, list[date]]]
):
    """Class to manage fetching Twente Milieu data."""

    def __init__(self, hass: HomeAssistant, entry: TwenteMilieuConfigEntry) -> None:
        """Initialize Twente Milieu data update coordinator."""
        self.twentemilieu = TwenteMilieu(
            post_code=entry.data[CONF_POST_CODE],
            house_number=entry.data[CONF_HOUSE_NUMBER],
            house_letter=entry.data[CONF_HOUSE_LETTER],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[WasteType, list[date]]:
        """Fetch Twente Milieu data."""
        try:
            return await self.twentemilieu.update()
        except TwenteMilieuConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except TwenteMilieuError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from err
