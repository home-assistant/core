"""NextBus data update coordinator."""

from datetime import timedelta
import logging
from typing import Any, cast

from py_nextbus import NextBusClient
from py_nextbus.client import NextBusFormatError, NextBusHTTPError, RouteStop

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import listify

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
        self.client = NextBusClient(output_format="json", agency=agency)
        self._agency = agency
        self._stop_routes: set[RouteStop] = set()
        self._predictions: dict[RouteStop, dict[str, Any]] = {}

    def add_stop_route(self, stop_tag: str, route_tag: str) -> None:
        """Tell coordinator to start tracking a given stop and route."""
        self._stop_routes.add(RouteStop(route_tag, stop_tag))

    def remove_stop_route(self, stop_tag: str, route_tag: str) -> None:
        """Tell coordinator to stop tracking a given stop and route."""
        self._stop_routes.remove(RouteStop(route_tag, stop_tag))

    def get_prediction_data(
        self, stop_tag: str, route_tag: str
    ) -> dict[str, Any] | None:
        """Get prediction result for a given stop and route."""
        return self._predictions.get(RouteStop(route_tag, stop_tag))

    def _calc_predictions(self, data: dict[str, Any]) -> None:
        self._predictions = {
            RouteStop(prediction["routeTag"], prediction["stopTag"]): prediction
            for prediction in listify(data.get("predictions", []))
        }

    def get_attribution(self) -> str | None:
        """Get attribution from api results."""
        return self.data.get("copyright")

    def has_routes(self) -> bool:
        """Check if this coordinator is tracking any routes."""
        return len(self._stop_routes) > 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from NextBus."""
        self.logger.debug("Updating data from API. Routes: %s", str(self._stop_routes))

        def _update_data() -> dict:
            """Fetch data from NextBus."""
            self.logger.debug("Updating data from API (executor)")
            try:
                data = self.client.get_predictions_for_multi_stops(self._stop_routes)
                # Casting here because we expect dict and not a str due to the input format selected being JSON
                data = cast(dict[str, Any], data)
                self._calc_predictions(data)
            except (NextBusHTTPError, NextBusFormatError) as ex:
                raise UpdateFailed("Failed updating nextbus data", ex) from ex
            return data

        return await self.hass.async_add_executor_job(_update_data)
