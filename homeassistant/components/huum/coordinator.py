"""DataUpdateCoordinator for Huum."""

from __future__ import annotations

from datetime import timedelta
import logging

from huum.exceptions import Forbidden, NotAuthenticated
from huum.huum import Huum
from huum.schemas import HuumStatusResponse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HuumDataUpdateCoordinator(DataUpdateCoordinator[HuumStatusResponse]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        huum: Huum,
        device_info: DeviceInfo,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

        self.huum = huum
        self.device_info = device_info

    async def _async_update_data(self) -> HuumStatusResponse:
        """Get the latest status data."""

        try:
            return await self.huum.status()
        except (Forbidden, NotAuthenticated) as err:
            _LOGGER.error("Could not log in to Huum with given credentials")
            raise ConfigEntryNotReady(
                "Could not log in to Huum with given credentials"
            ) from err
