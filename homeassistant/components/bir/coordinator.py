"""Data update coordinator for the BIR integration."""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict

from pybirno import BirClient, BirError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROPERTY_ID, DOMAIN, LOGGER, SCAN_INTERVAL, WASTE_TYPES

type BirConfigEntry = ConfigEntry[BirDataUpdateCoordinator]


class WastePickup(TypedDict):
    """Represent a waste pickup entry."""

    date: date
    days_until: int
    waste_type: str


class BirDataUpdateCoordinator(DataUpdateCoordinator[dict[str, WastePickup]]):
    """Class to manage fetching BIR data."""

    config_entry: BirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BirConfigEntry) -> None:
        """Initialize the BIR data update coordinator."""
        session = async_get_clientsession(hass)
        self.client = BirClient(entry.data[CONF_PROPERTY_ID], session)
        self.address: str = entry.data[CONF_ADDRESS]

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, WastePickup]:
        """Fetch data from BIR API."""
        try:
            pickups = await self.client.get_pickups()
        except BirError as err:
            raise UpdateFailed(f"Error communicating with BIR API: {err}") from err

        return self._process_pickup_data(pickups)

    @staticmethod
    def _process_pickup_data(
        pickups: list, reference_date: date | None = None
    ) -> dict[str, WastePickup]:
        """Process raw pickup data into structured format."""
        if reference_date is None:
            reference_date = datetime.now().date()

        next_pickups: dict[str, WastePickup] = {}

        for pickup in pickups:
            waste_key = pickup.waste_type
            if waste_key not in WASTE_TYPES:
                continue

            days_until = max(0, (pickup.date - reference_date).days)

            if (
                waste_key not in next_pickups
                or pickup.date < next_pickups[waste_key]["date"]
            ):
                next_pickups[waste_key] = WastePickup(
                    date=pickup.date,
                    days_until=days_until,
                    waste_type=waste_key,
                )

        return next_pickups
