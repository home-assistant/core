"""Coordinator for the Samsung ExLink integration."""

from datetime import timedelta
import logging
from typing import override

from samsung_exlink import SamsungTV, SamsungTVError, TVState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)

type SamsungExLinkConfigEntry = ConfigEntry[SamsungExLinkCoordinator]


class SamsungExLinkCoordinator(DataUpdateCoordinator[TVState | None]):
    """Poll and distribute Samsung TV state for the config entry."""

    def __init__(
        self, hass: HomeAssistant, config_entry: SamsungExLinkConfigEntry, tv: SamsungTV
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Samsung ExLink",
            update_interval=SCAN_INTERVAL,
        )
        self.tv = tv

    @override
    async def _async_update_data(self) -> TVState | None:
        """Refresh the TV state."""
        try:
            await self.tv.refresh()
        except (SamsungTVError, ConnectionError, OSError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        return self.tv.state
