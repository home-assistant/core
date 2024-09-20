"""Data UpdateCoordinator for the Portainer integration."""

from datetime import timedelta
import logging

from aiotainer.client import PortainerClient
from aiotainer.exceptions import ApiException, AuthException
from aiotainer.model import NodeData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class PortainerDataUpdateCoordinator(DataUpdateCoordinator[dict[int, NodeData]]):
    """Class to manage fetching data."""

    def __init__(
        self, hass: HomeAssistant, api: PortainerClient, entry: ConfigEntry
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

        self.ws_connected: bool = False

    async def _async_update_data(self) -> dict[int, NodeData]:
        """Subscribe for websocket and poll data from the API."""
        try:
            return await self.api.get_status()
        except ApiException as err:
            raise UpdateFailed(err) from err
        except AuthException as err:
            raise ConfigEntryAuthFailed(err) from err
