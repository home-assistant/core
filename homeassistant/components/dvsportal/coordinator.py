"""Coordinator for DVSPortal integration."""

from datetime import timedelta
import logging

from dvsportal import DVSPortal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .types import DVSPortalData

_LOGGER = logging.getLogger(__name__)


class DVSPortalCoordinator(DataUpdateCoordinator[DVSPortalData]):
    """Class to manage fetching data from the DVSPortal API."""

    def __init__(self, hass: HomeAssistant, dvs_portal: DVSPortal) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(minutes=5),
        )
        self.dvs_portal = dvs_portal

    async def _async_update_data(self) -> DVSPortalData:
        """Fetch data from the DVSPortal API."""
        try:
            await self.dvs_portal.update()
        except Exception as e:
            _LOGGER.exception("Error communicating with API")
            raise UpdateFailed("Error communicating with API") from e
        return {
            "default_code": self.dvs_portal.default_code,
            "default_type_id": self.dvs_portal.default_type_id,
            "balance": self.dvs_portal.balance,
            "active_reservations": self.dvs_portal.active_reservations,
            "historic_reservations": self.dvs_portal.historic_reservations,
            "known_license_plates": self.dvs_portal.known_license_plates,
        }
