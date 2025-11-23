"""DataUpdateCoordinator for Energenie Mi Home."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MiHomeAPI, MiHomeAuthError, MiHomeConnectionError, MiHomeDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Update interval: 60 seconds for cloud polling
UPDATE_INTERVAL = timedelta(seconds=60)


type MiHomeConfigEntry = ConfigEntry[MiHomeCoordinator]


class MiHomeCoordinator(DataUpdateCoordinator[dict[str, MiHomeDevice]]):
    """Class to manage fetching data from Mi Home API."""

    config_entry: MiHomeConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: MiHomeConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )

        session = async_get_clientsession(hass)
        self.api = MiHomeAPI(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
            session,
            api_key=config_entry.data.get(CONF_API_KEY),
        )

    async def _async_update_data(self) -> dict[str, MiHomeDevice]:
        """Fetch data from Mi Home API."""
        try:
            devices = await self.api.async_get_devices()
            device_dict = {device.device_id: device for device in devices}
            _LOGGER.debug(
                "Coordinator updated with %d devices: %s",
                len(device_dict),
                [f"{d.device_id}(available={d.available})" for d in devices],
            )
        except MiHomeAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (MiHomeConnectionError, Exception) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return device_dict
