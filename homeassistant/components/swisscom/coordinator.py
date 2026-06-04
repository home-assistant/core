"""DataUpdateCoordinator for the Swisscom Internet-Box."""

from datetime import timedelta
import logging

from swisscom_internet_box import (
    Device,
    SwisscomAuthError,
    SwisscomClient,
    SwisscomConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type SwisscomConfigEntry = ConfigEntry[SwisscomDataUpdateCoordinator]


class SwisscomDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Poll the Internet-Box for the list of LAN devices."""

    config_entry: SwisscomConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SwisscomConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.client = SwisscomClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch device data from the box."""
        try:
            devices = await self.client.get_devices()
        except SwisscomAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SwisscomConnectionError as err:
            raise UpdateFailed(str(err)) from err

        return {device.key: device for device in devices if device.key}
