"""DataUpdateCoordinator for DD-WRT."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_WIRELESS_ONLY, DOMAIN
from .router import DdWrtClients, DdWrtConnectionError, DdWrtRouter

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type DdWrtConfigEntry = ConfigEntry[DdWrtDataUpdateCoordinator]


class DdWrtDataUpdateCoordinator(DataUpdateCoordinator[DdWrtClients]):
    """Class to manage fetching data from a DD-WRT router."""

    config_entry: DdWrtConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: DdWrtConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.router = DdWrtRouter(
            self.host,
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            use_ssl=config_entry.data[CONF_SSL],
            verify_ssl=config_entry.data[CONF_VERIFY_SSL],
            wireless_only=config_entry.data[CONF_WIRELESS_ONLY],
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> DdWrtClients:
        """Fetch the connected clients from the DD-WRT router."""
        try:
            return await self.hass.async_add_executor_job(self.router.get_clients)
        except DdWrtConnectionError as err:
            raise UpdateFailed(
                f"Failed to fetch data from DD-WRT router {self.host}"
            ) from err
