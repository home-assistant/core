"""NextBus data update coordinator."""

from datetime import timedelta
import logging
from typing import Any

from py_nextbus import NextBusClient
from py_nextbus.client import NextBusFormatError, NextBusHTTPError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import RouteStop

_LOGGER = logging.getLogger(__name__)


class NextBusDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching NextBus data."""

    def __init__(self, hass: HomeAssistant, agency: str) -> None:
        """Initialize a global coordinator for fetching data for a given agency."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = NextBusClient(agency_id=agency)
        self._agency = agency
        self._route_stops: set[RouteStop] = set()
        self._predictions: dict[RouteStop, dict[str, Any]] = {}

    def add_stop_route(self, stop_id: str, route_id: str) -> None:
        """Tell coordinator to start tracking a given stop and route."""
        self._route_stops.add(RouteStop(route_id, stop_id))

    def remove_stop_route(self, stop_id: str, route_id: str) -> None:
        """Tell coordinator to stop tracking a given stop and route."""
        self._route_stops.remove(RouteStop(route_id, stop_id))

    def get_prediction_data(self, stop_id: str, route_id: str) -> dict[str, Any] | None:
        """Get prediction result for a given stop and route."""
        return self._predictions.get(RouteStop(route_id, stop_id))

    def has_routes(self) -> bool:
        """Check if this coordinator is tracking any routes."""
        return len(self._route_stops) > 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from NextBus."""
        self.logger.debug("Updating data from API. Routes: %s", str(self._route_stops))

        def _update_data() -> dict:
            """Fetch data from NextBus."""
            self.logger.debug("Updating data from API (executor)")
            predictions: dict[RouteStop, dict[str, Any]] = {}
            for route_stop in self._route_stops:
                prediction_results: list[dict[str, Any]] = []
                try:
                    prediction_results = self.client.predictions_for_stop(
                        route_stop.stop_id, route_stop.route_id
                    )
                except (NextBusHTTPError, NextBusFormatError) as ex:
                    raise UpdateFailed("Failed updating nextbus data", ex) from ex

                if prediction_results:
                    predictions[route_stop] = prediction_results[0]
            self._predictions = predictions

            return predictions

        return await self.hass.async_add_executor_job(_update_data)
