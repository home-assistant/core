"""Data update coordinator for ReCollect Waste."""

from __future__ import annotations

from datetime import date, timedelta

from aiorecollect.client import Client, PickupEvent
from aiorecollect.errors import RecollectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(days=1)


class ReCollectWasteDataUpdateCoordinator(DataUpdateCoordinator[list[PickupEvent]]):
    """Class to manage fetching ReCollect Waste data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=(
                f"Place {config_entry.data[CONF_PLACE_ID]}, "
                f"Service {config_entry.data[CONF_SERVICE_ID]}"
            ),
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self._client = Client(
            config_entry.data[CONF_PLACE_ID],
            config_entry.data[CONF_SERVICE_ID],
            session=aiohttp_client.async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> list[PickupEvent]:
        """Fetch data from ReCollect."""
        try:
            # Retrieve today through to 35 days in the future, to get
            # coverage across a full two months boundary so that no
            # upcoming pickups are missed. The api.recollect.net base API
            # call returns only the current month when no dates are passed.
            # This ensures that data about when the next pickup is will be
            # returned when the next pickup is the first day of the next month.
            # Ex: Today is August 31st, tomorrow is a pickup on September 1st.
            today = date.today()
            return await self._client.async_get_pickup_events(
                start_date=today,
                end_date=today + timedelta(days=35),
            )
        except RecollectError as err:
            raise UpdateFailed(
                f"Error while requesting data from ReCollect: {err}"
            ) from err
