"""DataUpdateCoordinator for HDFury Integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=60)

type HDFuryConfigEntry = ConfigEntry[HDFuryCoordinator]


@dataclass(kw_only=True, frozen=True)
class HDFuryData:
    """HDFury Data Class."""

    board: dict[str, str]
    info: dict[str, str]
    config: dict[str, str]


class HDFuryCoordinator(DataUpdateCoordinator[HDFuryData]):
    """HDFury Device Coordinator Class."""

    def __init__(self, hass: HomeAssistant, entry: HDFuryConfigEntry) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="HDFury",
            update_interval=SCAN_INTERVAL,
        )
        self.host: str = entry.data[CONF_HOST]
        self.client = HDFuryAPI(self.host, async_get_clientsession(hass))

    async def _async_update_data(self) -> HDFuryData:
        """Fetch the latest device data."""

        try:
            board = await self.client.get_board()
            info = await self.client.get_info()
            config = await self.client.get_config()
        except HDFuryError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        return HDFuryData(
            board=board,
            info=info,
            config=config,
        )
