"""DataUpdateCoordinator for UniFi AP Direct."""

from datetime import timedelta
import logging
from typing import override

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SSH_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type UniFiDirectConfigEntry = ConfigEntry[UniFiDirectDataUpdateCoordinator]


class UniFiDirectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching data from the UniFi AP."""

    config_entry: UniFiDirectConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: UniFiDirectConfigEntry
    ) -> None:
        """Initialize the coordinator using config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.ap = UniFiAP(
            target=self.host,
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            port=config_entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data from the UniFi AP."""
        try:
            return await self.hass.async_add_executor_job(self.ap.get_clients)
        except (UniFiAPConnectionException, UniFiAPDataException) as err:
            raise UpdateFailed(
                f"Failed to fetch data from UniFi AP {self.host}"
            ) from err
