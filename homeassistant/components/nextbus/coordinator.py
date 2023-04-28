"""NextBus data update coordinator."""
from datetime import timedelta
from json.decoder import JSONDecodeError
import logging
from typing import Any, NamedTuple
from urllib.error import HTTPError

from py_nextbus import NextBusClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import listify

_LOGGER = logging.getLogger(__name__)


class StopRoute(NamedTuple):
    """Contains a stop and a route tag for looking up predictions."""

    stop_tag: str
    route_tag: str


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
        self._stop_routes: set[StopRoute] = set()
        self._data: dict[str, Any] = {}

    def add_stop_route(self, stop_tag: str, route_tag: str) -> None:
        """Tell coordinator to start tracking a given stop and route."""
        self._stop_routes.add(StopRoute(stop_tag, route_tag))

    def remove_stop_route(self, stop_tag: str, route_tag: str) -> None:
        """Tell coordinator to stop tracking a given stop and route."""
        self._stop_routes.remove(StopRoute(stop_tag, route_tag))

    def get_prediction_data(
        self, stop_tag: str, route_tag: str
    ) -> dict[str, Any] | None:
        """Get prediction result for a given stop and route."""
        for prediction in listify(self.data.get("predictions", [])):
            if (
                prediction["stopTag"] == stop_tag
                and prediction["routeTag"] == route_tag
            ):
                return prediction

        return None

    def has_routes(self) -> bool:
        """Check if this coordinator is tracking any routes."""
        return len(self._stop_routes) > 0

    async def _async_update_data(self) -> dict:
        """Fetch data from NextBus."""
        self.logger.debug("Updating data from API. Routes: %s", str(self._stop_routes))

        def _update_data() -> dict:
            """Fetch data from NextBus."""
            self.logger.debug("Updating data from API (executor)")
            try:
                return self.client.get_predictions_for_multi_stops(
                    [sr._asdict() for sr in self._stop_routes]
                )
            except HTTPError as ex:
                raise UpdateFailed("failed connecting to nextbus api", ex) from ex
            except JSONDecodeError as ex:
                raise UpdateFailed(
                    "failed reading response from nextbus api", ex
                ) from ex
            except Exception as ex:
                raise UpdateFailed("failed updating nextbus data", ex) from ex

        return await self.hass.async_add_executor_job(_update_data)
