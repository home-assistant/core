"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME

_LOGGER = logging.getLogger(__name__)

# To trigger appropriate actions on power on and power off we need the same time
INTERVAL = timedelta(seconds=5)


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    def __init__(self, hass: HomeAssistant, device: JvcProjector) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=NAME,
            update_interval=INTERVAL,
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

        _LOGGER.debug(
            "JVC Projector - get_state = power %s - input %s",
            state["power"],
            state["input"],
        )

        return state
