"""NextBus data update coordinator."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

from py_nextbus import NextBusClient
from py_nextbus.client import NextBusFormatError, NextBusHTTPError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import RouteStop

_LOGGER = logging.getLogger(__name__)

# At what percentage of the request limit should the coordinator pause making requests
UPDATE_INTERVAL_SECONDS = 30
THROTTLE_PRECENTAGE = 80


class NextBusDataUpdateCoordinator(
    DataUpdateCoordinator[dict[RouteStop, dict[str, Any]]]
):
    """Class to manage fetching NextBus data."""

    def __init__(self, hass: HomeAssistant, agency: str) -> None:
        """Initialize a global coordinator for fetching data for a given agency."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,  # It is shared between multiple entries
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
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

    @override
    async def _async_update_data(self) -> dict[RouteStop, dict[str, Any]]:
        """Fetch data from NextBus."""

        if (
            # If we have predictions, check the rate limit
            self._predictions
            # If are over our rate limit percentage, we should throttle
            and self.client.rate_limit_percent >= THROTTLE_PRECENTAGE
            # But only if we have a reset time to unthrottle
            and self.client.rate_limit_reset is not None
            # Unless we are after the reset time
            and datetime.now() < self.client.rate_limit_reset
        ):
            self.logger.debug(
                "Rate limit threshold reached. Skipping updates for. Routes: %s",
                str(self._route_stops),
            )
            return self._predictions

        _stops_to_route_stops: dict[str, set[RouteStop]] = {}
        for route_stop in self._route_stops:
            _stops_to_route_stops.setdefault(route_stop.stop_id, set()).add(route_stop)

        self.logger.debug(
            "Updating data from API. Routes: %s", str(_stops_to_route_stops)
        )

        def _update_data() -> dict[RouteStop, dict[str, Any]]:
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
