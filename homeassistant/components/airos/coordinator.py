"""DataUpdateCoordinator for AirOS."""

from __future__ import annotations

import logging

from airos.airos8 import AirOS8, AirOS8Data
from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDataMissingError,
    AirOSDeviceConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type AirOSConfigEntry = ConfigEntry[AirOSDataUpdateCoordinator]


class AirOSDataUpdateCoordinator(DataUpdateCoordinator[AirOS8Data]):
    """Class to manage fetching AirOS data from single endpoint."""

    config_entry: AirOSConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: AirOSConfigEntry, airos_device: AirOS8
    ) -> None:
        """Initialize the coordinator."""
        self.airos_device = airos_device
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> AirOS8Data:
        """Fetch data from AirOS."""
        try:
            await self.airos_device.login()
            return await self.airos_device.status()
        except (AirOSConnectionAuthenticationError,) as err:
            _LOGGER.exception("Error authenticating with airOS device")
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except (
            AirOSConnectionSetupError,
            AirOSDeviceConnectionError,
            TimeoutError,
        ) as err:
            _LOGGER.error("Error connecting to airOS device: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except (AirOSDataMissingError,) as err:
            _LOGGER.error("Expected data not returned by airOS device: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_data_missing",
            ) from err
