"""DataUpdateCoordinator for UniFi AP Direct."""

from datetime import timedelta
import logging

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SSH_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type UnifiDirectConfigEntry = ConfigEntry[UniFiDirectDataUpdateCoordinator]


class UniFiDirectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching data from the UniFi AP."""

    config_entry: UnifiDirectConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: UnifiDirectConfigEntry
    ) -> None:
        """Initialize the coordinator using a config entry."""
        self.config_entry = config_entry
        self.host = config_entry.data[CONF_HOST]
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]
        self.port = config_entry.data.get(CONF_PORT, DEFAULT_SSH_PORT)

        self.ap = UniFiAP(
            target=self.host,
            username=self.username,
            password=self.password,
            port=self.port,
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from the UniFi AP."""
        try:
            return await self.hass.async_add_executor_job(self.ap.get_clients)
        except (UniFiAPConnectionException, UniFiAPDataException) as err:
            raise UpdateFailed(
                f"Failed to fetch data from UniFi AP {self.host}"
            ) from err
