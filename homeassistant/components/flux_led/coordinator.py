"""The Flux LED/MagicLight integration coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from flux_led.aio import AIOWifiLedBulb

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import FLUX_LED_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)


REQUEST_REFRESH_DELAY: Final = 2.0


class FluxLedUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a specific flux_led device."""

    def __init__(
        self, hass: HomeAssistant, device: AIOWifiLedBulb, entry: ConfigEntry
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.device = device
        self.title = entry.title
        self.entry = entry
        self.force_next_update = False
        super().__init__(
            hass,
            _LOGGER,
            name=self.device.ipaddr,
            update_interval=timedelta(seconds=10),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
            always_update=False,
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.async_update(force=self.force_next_update)
        except FLUX_LED_EXCEPTIONS as ex:
            raise UpdateFailed(ex) from ex
        finally:
            self.force_next_update = False
