"""The IntelliFire integration."""

from __future__ import annotations

from datetime import timedelta

import aiohttp
from intellifire4py import UnifiedFireplace
from intellifire4py.control import IntelliFireController
from intellifire4py.model import IntelliFirePollData
from intellifire4py.read import IntelliFireDataProvider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type IntellifireConfigEntry = ConfigEntry[IntellifireDataUpdateCoordinator]


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator[IntelliFirePollData]):
    """Class to manage the polling of the fireplace API."""

    config_entry: IntellifireConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IntellifireConfigEntry,
        fireplace: UnifiedFireplace,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )

        self.fireplace = fireplace

    @property
    def read_api(self) -> IntelliFireDataProvider:
        """Return the Status API pointer."""
        return self.fireplace.read_api

    @property
    def control_api(self) -> IntelliFireController:
        """Return the control API."""
        return self.fireplace.control_api

    async def _async_update_data(self) -> IntelliFirePollData:
        try:
            await self.fireplace.perform_poll()
        except aiohttp.ClientResponseError as err:
            if err.status == 403:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            raise UpdateFailed(f"Error communicating with fireplace: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with fireplace: {err}") from err
        return self.fireplace.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            manufacturer="Hearth and Home",
            model="IFT-WFM",
            name="IntelliFire",
            identifiers={("IntelliFire", str(self.fireplace.serial))},
            configuration_url=f"http://{self.fireplace.ip_address}/poll",
        )
