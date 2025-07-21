"""DataUpdateCoordinator for AirOS."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from airos.airos8 import AirOS
from airos.exceptions import (
    ConnectionAuthenticationError,
    ConnectionSetupError,
    DataMissingError,
    DeviceConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AIROS_DEFAULT_HOSTNAME,
    AIROS_DEVICE_ID_KEY,
    AIROS_HOST_KEY,
    AIROS_HOSTNAME_KEY,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type AirOSConfigEntry = ConfigEntry[AirOSDataUpdateCoordinator]


@dataclass
class AirOSData:
    """AirOS data stored in the DataUpdateCoordinator."""

    device_data: dict[str, Any]
    device_id: str
    hostname: str


class AirOSDataUpdateCoordinator(DataUpdateCoordinator[AirOSData]):
    """Class to manage fetching AirOS data from single endpoint."""

    config_entry: AirOSConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: AirOSConfigEntry, airos_device: AirOS
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

    async def _async_update_data(self) -> AirOSData:
        """Fetch data from AirOS."""
        try:
            await self.airos_device.login()
            status = await self.airos_device.status()
        except (ConnectionAuthenticationError,) as err:
            _LOGGER.exception("Error authenticating with airOS device: %s")
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except (ConnectionSetupError, DeviceConnectionError, TimeoutError) as err:
            _LOGGER.error("Error connecting to airOS device: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except (DataMissingError,) as err:
            _LOGGER.error("Expected data not returned by airOS device: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_data_missing",
            ) from err

        host_data = status[AIROS_HOST_KEY]
        device_id = host_data[AIROS_DEVICE_ID_KEY]
        hostname = host_data.get(AIROS_HOSTNAME_KEY, AIROS_DEFAULT_HOSTNAME)

        return AirOSData(device_data=status, device_id=device_id, hostname=hostname)
