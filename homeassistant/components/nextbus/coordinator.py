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

    async def async_shutdown(self) -> None:
        """If there are no more routes, cancel any scheduled call, and ignore new runs."""
        if self.has_routes():
            return

        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from NextBus."""

        _stops_to_route_stops: dict[str, set[RouteStop]] = {}
        for route_stop in self._route_stops:
            _stops_to_route_stops.setdefault(route_stop.stop_id, set()).add(route_stop)

        self.logger.debug(
            "Updating data from API. Routes: %s", str(_stops_to_route_stops)
        )

        def _update_data() -> dict:
            """Fetch data from NextBus."""
            self.logger.debug("Updating data from API (executor)")
            predictions: dict[RouteStop, dict[str, Any]] = {}

            for stop_id, route_stops in _stops_to_route_stops.items():
                self.logger.debug("Updating data from API (executor) %s", stop_id)
                try:
                    prediction_results = self.client.predictions_for_stop(stop_id)
                except NextBusHTTPError as ex:
                    self.logger.error(
                        "Error updating %s (executor): %s %s",
                        str(stop_id),
                        ex,
                        getattr(ex, "response", None),
                    )
                    raise UpdateFailed("Failed updating nextbus data", ex) from ex
                except NextBusFormatError as ex:
                    raise UpdateFailed("Failed updating nextbus data", ex) from ex

                self.logger.debug(
                    "Prediction results for %s (executor): %s",
                    str(stop_id),
                    str(prediction_results),
                )

                for route_stop in route_stops:
                    for prediction_result in prediction_results:
                        if (
                            prediction_result["stop"]["id"] == route_stop.stop_id
                            and prediction_result["route"]["id"] == route_stop.route_id
                        ):
                            predictions[route_stop] = prediction_result
                            break
                    else:
                        self.logger.warning(
                            "Prediction not found for %s (executor)", str(route_stop)
                        )

            self._predictions = predictions

            return predictions

        return await self.hass.async_add_executor_job(_update_data)
