"""Coordinator for Fresh-r integration."""

from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientError
from pyfreshr import FreshrClient
from pyfreshr.exceptions import ApiResponseError, LoginError
from pyfreshr.models import DeviceReadings, DeviceSummary

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

DEVICES_SCAN_INTERVAL = timedelta(hours=1)
READINGS_SCAN_INTERVAL = timedelta(minutes=10)


@dataclass
class FreshrData:
    """Runtime data stored on the config entry."""

    devices: FreshrDevicesCoordinator
    readings: dict[str, FreshrReadingsCoordinator]


type FreshrConfigEntry = ConfigEntry[FreshrData]


class FreshrDevicesCoordinator(DataUpdateCoordinator[list[DeviceSummary]]):
    """Coordinator that refreshes the device list once an hour."""

    config_entry: FreshrConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: FreshrConfigEntry) -> None:
        """Initialize the device list coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_devices",
            update_interval=DEVICES_SCAN_INTERVAL,
        )
        self.client = FreshrClient(session=async_create_clientsession(hass))

    async def _async_update_data(self) -> list[DeviceSummary]:
        """Fetch the list of devices from the Fresh-r API."""
        username = self.config_entry.data[CONF_USERNAME]
        password = self.config_entry.data[CONF_PASSWORD]

        try:
            if not self.client.logged_in:
                await self.client.login(username, password)

            devices = await self.client.fetch_devices()
        except LoginError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except (ApiResponseError, ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        else:
            return devices


class FreshrReadingsCoordinator(DataUpdateCoordinator[DeviceReadings]):
    """Coordinator that refreshes readings for a single device every 10 minutes."""

    config_entry: FreshrConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FreshrConfigEntry,
        device: DeviceSummary,
        client: FreshrClient,
    ) -> None:
        """Initialize the readings coordinator for a single device."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_readings_{device.id}",
            update_interval=READINGS_SCAN_INTERVAL,
        )
        self._device = device
        self._client = client

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self._device.id

    async def _async_update_data(self) -> DeviceReadings:
        """Fetch current readings for this device from the Fresh-r API."""
        try:
            return await self._client.fetch_device_current(self._device)
        except LoginError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except (ApiResponseError, ClientError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
