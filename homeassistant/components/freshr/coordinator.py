"""Coordinator for Fresh-r integration."""

from datetime import timedelta

from aiohttp import ClientError
from pyfreshr import FreshrClient
from pyfreshr.exceptions import LoginError, ScrapeError
from pyfreshr.models import DeviceReadings

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type FreshrConfigEntry = ConfigEntry[FreshrCoordinator]

SCAN_INTERVAL = timedelta(minutes=60)


class FreshrCoordinator(DataUpdateCoordinator[dict[str, DeviceReadings]]):
    """Fresh-r update coordinator."""

    config_entry: FreshrConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: FreshrConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._client = FreshrClient(session=async_create_clientsession(hass))

    async def _async_update_data(self) -> dict[str, DeviceReadings]:
        """Fetch data from Fresh-r API.

        Returns a dict mapping device serial to DeviceReadings.
        """
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]

        try:
            if not self._client.logged_in:
                await self._client.login(username, password)

            devices = await self._client.fetch_devices()
            if not devices:
                raise UpdateFailed("No devices found")

            results: dict[str, DeviceReadings] = {}
            for device in devices:
                if device.id:
                    current = await self._client.fetch_device_current(device)
                    results[device.id] = current
        except LoginError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except (ScrapeError, ClientError) as err:
            raise UpdateFailed(f"API communication error: {err}") from err
        else:
            return results
