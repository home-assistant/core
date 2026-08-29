"""DataUpdateCoordinator for Arris TG2492LG."""

from datetime import timedelta
import logging
from typing import override

from aiohttp.client_exceptions import ClientError
from arris_tg2492lg import ConnectBox, Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type ArrisConfigEntry = ConfigEntry[ArrisDataUpdateCoordinator]


class ArrisDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from the Arris TG2492LG router."""

    config_entry: ArrisConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ArrisConfigEntry) -> None:
        """Initialize the coordinator using config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.connect_box = ConnectBox(
            async_get_clientsession(hass),
            f"http://{self.host}",
            config_entry.data[CONF_PASSWORD],
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from the Arris TG2492LG router."""
        try:
            devices = await self.connect_box.async_get_connected_devices()
        except ClientError as err:
            raise UpdateFailed(
                f"Failed to fetch data from Arris TG2492LG router {self.host}"
            ) from err

        return {
            device.mac: device for device in devices if device.online and device.mac
        }
