"""The AccuWeather coordinator."""

from asyncio import timeout
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from accuweather import AccuWeather, ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp.client_exceptions import ClientConnectorError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class AccuWeatherDataUpdateCoordinator(TimestampDataUpdateCoordinator[Any]):
    """Class to manage fetching AccuWeather data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        accuweather: AccuWeather,
        name: str,
        coordinator_type: str,
        update_interval: timedelta,
        update_method: str,
    ) -> None:
        """Initialize."""
        self.accuweather = accuweather
        self._update_method = update_method

        if TYPE_CHECKING:
            assert accuweather.location_key is not None

        self.location_key = accuweather.location_key
        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.location_key)},
            manufacturer=MANUFACTURER,
            name=name,
            # You don't need to provide specific details for the URL,
            # so passing in _ characters is fine if the location key
            # is correct
            configuration_url=(
                "http://accuweather.com/en/"
                f"_/_/{self.location_key}/"
                f"weather-forecast/{self.location_key}/"
            ),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} ({coordinator_type})",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        update_method = getattr(self.accuweather, self._update_method)
        try:
            async with timeout(10):
                result = await update_method()
        except (
            ApiError,
            ClientConnectorError,
            InvalidApiKeyError,
            RequestsExceededError,
        ) as error:
            raise UpdateFailed(error) from error

        _LOGGER.debug("Requests remaining: %d", self.accuweather.requests_remaining)

        return result
