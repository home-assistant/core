"""Coordinator for DVSPortal integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from dvsportal import DVSPortal, HistoricReservation, Reservation

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class DVSPortalData:
    """Data class for DVSPortal coordinator data."""

    default_code: str | None
    default_type_id: int | None
    balance: float | None
    active_reservations: dict[str, Reservation]
    historic_reservations: dict[str, HistoricReservation]
    known_license_plates: dict[str, str]  # historic, saved or reserved license plates


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

        return DVSPortalData(
            default_code=self.dvs_portal.default_code,
            default_type_id=self.dvs_portal.default_type_id,
            balance=self.dvs_portal.balance,
            active_reservations=self.dvs_portal.active_reservations,
            historic_reservations=self.dvs_portal.historic_reservations,
            known_license_plates=self.dvs_portal.known_license_plates,
        )
