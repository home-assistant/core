"""Component to embed TP-Link smart home devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from kasa import AuthenticationException, SmartDevice, SmartDeviceException

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35


class TPLinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a specific TPLink device."""

    config_entry: config_entries.ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device: SmartDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            name=device.host,
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.update(update_children=False)
        except AuthenticationException as ex:
            raise ConfigEntryAuthFailed from ex
        except SmartDeviceException as ex:
            raise UpdateFailed(ex) from ex
