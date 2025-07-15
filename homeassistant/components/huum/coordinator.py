"""DataUpdateCoordinator for Huum."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from huum.exceptions import Forbidden, NotAuthenticated
from huum.huum import Huum
from huum.schemas import HuumStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HuumDataUpdateCoordinator(DataUpdateCoordinator[HuumStatusResponse]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
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
            raise ConfigEntryNotReady(
                "Could not log in to Huum with given credentials"
            ) from err

    def convert_timestamp(self, timestamp: int | None) -> datetime | None:
        """Convert numeric timestamp to datetime object."""
        if timestamp:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        return None
