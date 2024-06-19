"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from jvcprojector import (
    JvcProjector,
    JvcProjectorAuthError,
    JvcProjectorConnectError,
    const,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME

_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device = device
        self.unique_id = format_mac(device.mac)

    async def _async_update_data(self) -> dict[str, str]:
        """Get the latest state data."""
        try:
            state = await self.device.get_state()
        except JvcProjectorConnectError as err:
            raise UpdateFailed(f"Unable to connect to {self.device.host}") from err
        except JvcProjectorAuthError as err:
            raise ConfigEntryAuthFailed("Password authentication failed") from err

        old_interval = self.update_interval

        if state[const.POWER] != const.STANDBY:
            self.update_interval = INTERVAL_FAST
        else:
            self.update_interval = INTERVAL_SLOW

        if self.update_interval != old_interval:
            _LOGGER.debug("Changed update interval to %s", self.update_interval)

        return state
