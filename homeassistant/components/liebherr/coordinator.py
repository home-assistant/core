"""DataUpdateCoordinator for Liebherr integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from pyliebherrhomeapi import (
    DeviceState,
    LiebherrAuthenticationError,
    LiebherrClient,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class LiebherrData:
    """Runtime data for the Liebherr integration."""

    client: LiebherrClient
    coordinators: dict[str, LiebherrCoordinator] = field(default_factory=dict)


type LiebherrConfigEntry = ConfigEntry[LiebherrData]


class LiebherrCoordinator(DataUpdateCoordinator[DeviceState]):
    """Class to manage fetching Liebherr data from the API for a single device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LiebherrConfigEntry,
        client: LiebherrClient,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.device_id = device_id

    async def _async_setup(self) -> None:
        """Set up the coordinator by validating device access."""
        try:
            await self.client.get_device(self.device_id)
        except LiebherrAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except LiebherrConnectionError as err:
            raise ConfigEntryNotReady(
                f"Failed to connect to device {self.device_id}: {err}"
            ) from err

    async def _async_update_data(self) -> DeviceState:
        """Fetch data from API for this device."""
        try:
            return await self.client.get_device_state(self.device_id)
        except LiebherrAuthenticationError as err:
            raise ConfigEntryAuthFailed("API key is no longer valid") from err
        except LiebherrTimeoutError as err:
            raise UpdateFailed(
                f"Timeout communicating with device {self.device_id}"
            ) from err
        except LiebherrConnectionError as err:
            raise UpdateFailed(
                f"Error communicating with device {self.device_id}"
            ) from err
