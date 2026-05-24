"""DataUpdateCoordinator for UniFi AP Direct."""

from datetime import timedelta
import logging
from typing import Any

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SSH_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


def validate_connection(host: str, username: str, password: str, port: int) -> None:
    """Validate the connection to the UniFi AP.

    Raises ConnectionError on failure.
    """
    try:
        ap = UniFiAP(target=host, username=username, password=password, port=port)
        ap.get_clients()
    except (UniFiAPConnectionException, UniFiAPDataException) as err:
        raise ConnectionError("Failed to connect to UniFi AP") from err


def validate_connection_data(data: dict[str, Any]) -> None:
    """Validate connection using a config-style dict.

    Kept for config flow compatibility.
    """
    validate_connection(
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get("port", DEFAULT_SSH_PORT),
    )


class UniFiDirectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Class to manage fetching data from the UniFi AP."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator using a config entry."""
        self.config_entry = config_entry
        self.host = config_entry.data.get(CONF_HOST)
        self.username = config_entry.data.get(CONF_USERNAME)
        self.password = config_entry.data.get(CONF_PASSWORD)
        self.port = config_entry.data.get("port", DEFAULT_SSH_PORT)

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
