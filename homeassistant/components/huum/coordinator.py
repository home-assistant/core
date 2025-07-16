"""DataUpdateCoordinator for Huum."""

from __future__ import annotations

from datetime import timedelta
import logging

from huum.exceptions import Forbidden, NotAuthenticated
from huum.huum import Huum
from huum.schemas import HuumStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = 30


class HuumDataUpdateCoordinator(DataUpdateCoordinator[HuumStatusResponse]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.huum = Huum(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        )

        # Be compatible with unique_ids previously set. To not create new devices all over the place.
        self.unique_id = config_entry.unique_id or config_entry.entry_id
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name="Huum sauna",
            manufacturer="Huum",
            model="UKU WiFi",
        )

    async def _async_update_data(self) -> HuumStatusResponse:
        """Get the latest status data."""

        try:
            return await self.huum.status()
        except (Forbidden, NotAuthenticated) as err:
            _LOGGER.error("Could not log in to Huum with given credentials")
            raise UpdateFailed(
                "Could not log in to Huum with given credentials"
            ) from err
