"""Coordinator object for the Rachio integration."""

from datetime import timedelta
import logging

from rachiopy import Rachio
from requests.exceptions import Timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, KEY_ID, KEY_VALVES

_LOGGER = logging.getLogger(__name__)

UPDATE_DELAY_TIME = 8


class RachioUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator Class for Rachio Hose Timers."""

    def __init__(
        self,
        hass: HomeAssistant,
        rachio: Rachio,
        base_station,
        base_count: int,
    ) -> None:
        """Initialize the Rachio Update Coordinator."""
        self.hass = hass
        self.rachio: Rachio = rachio
        self.base_station = base_station
        # To avoid exceeding the rate limit, increase polling interval for
        # each additional base station on the account
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} update coordinator",
            update_interval=timedelta(minutes=(base_count + 1)),
            # Debouncer used because the API takes a bit to update state changes
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=UPDATE_DELAY_TIME, immediate=False
            ),
        )

    async def _async_update_data(self) -> dict:
        """Update smart hose timer data."""
        try:
            data = await self.hass.async_add_executor_job(
                self.rachio.valve.list_valves, self.base_station[KEY_ID]
            )
        except Timeout as err:
            raise UpdateFailed(f"Could not connect to the Rachio API: {err}") from err
        valves = data[1][KEY_VALVES]
        return {valve[KEY_ID]: valve for valve in valves}
