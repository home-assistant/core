"""Data update coordinator for Harman Luxury."""

from datetime import datetime, timedelta
import logging
from typing import override

from aioharmanluxury import (
    DeviceInfo,
    HarmanLuxuryClient,
    HarmanLuxuryError,
    HarmanLuxuryState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type HarmanLuxuryConfigEntry = ConfigEntry[HarmanLuxuryCoordinator]

_SCAN_INTERVAL = timedelta(seconds=10)


class HarmanLuxuryCoordinator(DataUpdateCoordinator[HarmanLuxuryState]):
    """Poll a Harman Luxury device for its live player state."""

    config_entry: HarmanLuxuryConfigEntry
    device_info: DeviceInfo
    position_updated_at: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HarmanLuxuryConfigEntry,
        client: HarmanLuxuryClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=_SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_setup(self) -> None:
        """Fetch static device identity once."""
        try:
            self.device_info = await self.client.async_get_info()
        except HarmanLuxuryError as err:
            raise UpdateFailed(str(err)) from err
        if self.device_info.serial != self.config_entry.unique_id:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unexpected_device",
            )

    @override
    async def _async_update_data(self) -> HarmanLuxuryState:
        """Fetch the latest player state."""
        try:
            state = await self.client.async_get_state()
        except HarmanLuxuryError as err:
            raise UpdateFailed(str(err)) from err
        self.position_updated_at = (
            dt_util.utcnow() if state.position is not None else None
        )
        return state
