"""CityBus data update coordinator."""

from datetime import timedelta
import logging
from typing import Any

from citybussin import Citybussin

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import RouteStop

_LOGGER = logging.getLogger(__name__)


class CityBusDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching CityBus data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a global coordinator for fetching data."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.citybussin = Citybussin()
        self._route_stops: set[RouteStop] = set()
        self._estimates: dict[RouteStop, dict[str, Any]] = {}

    def add_route_stop(self, route_key: str, direction_key: str, stop_code: str) -> None:
        """Tell coordinator to start tracking a given stop for a route and direction."""
        self._route_stops.add(RouteStop(route_key, direction_key, stop_code))
    
    def remove_route_stop(self, route_key: str, direction_key: str, stop_code: str) -> None:
        """Tell coordinator to stop tracking a given stop for a route and direction."""
        self._route_stops.remove(RouteStop(route_key, direction_key, stop_code))

    def get_estimate_data(self, route_key: str, direction_key: str, stop_code: str) -> dict[str, Any] | None:
        """Get the estimate data for a given stop for a route and direction."""
        return self._estimates.get(RouteStop(route_key, direction_key, stop_code))
    
    def has_route_stops(self) -> bool:
        """Check if this coordinator is tracking any route stops."""
        return len(self._route_stops) > 0
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from CityBus."""

        def _update_data() -> dict:
            """Fetch data from CityBus."""
            self.logger.debug("Updating data from API (executor)")
            estimates: dict[RouteStop, dict[str, Any]] = {}

            for route_stop in self._route_stops:
                try:
                    estimates[route_stop] = self.citybussin.get_next_depart_times(
                        route_stop.route_key, route_stop.direction_key, route_stop.stop_code
                    )
                except Exception as err:
                    raise UpdateFailed(f"Error fetching data for CityBus stop {route_stop}: {err}") from err
            
            self._estimates = estimates
            return estimates

        return await self.hass.async_add_executor_job(_update_data)