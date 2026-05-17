"""DataUpdateCoordinator for the Zendure Smart Meter P1 integration."""

from typing import TYPE_CHECKING

from zendure_p1 import (
    Report,
    ZendureP1Client,
    ZendureP1ConnectionError,
    ZendureP1ResponseError,
    ZendureP1TimeoutError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import ZendureP1ConfigEntry


class ZendureP1Coordinator(DataUpdateCoordinator[Report]):
    """Coordinator for the Zendure Smart Meter P1."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZendureP1ConfigEntry,
        api: ZendureP1Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> Report:
        """Fetch data from api."""
        try:
            return await self.api.get_report()
        except ZendureP1ConnectionError as ex:
            raise UpdateFailed(
                f"Error communicating with the Zendure P1 device: {ex}"
            ) from ex
        except ZendureP1TimeoutError as ex:
            raise UpdateFailed(
                f"Timeout communicating with the Zendure P1 device: {ex}"
            ) from ex
        except ZendureP1ResponseError as ex:
            raise UpdateFailed(
                f"Invalid response from the Zendure P1 device: {ex}"
            ) from ex
