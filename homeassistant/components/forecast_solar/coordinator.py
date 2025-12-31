"""DataUpdateCoordinator for the Forecast.Solar integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from forecast_solar import Estimate, ForecastSolar, ForecastSolarConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    CONF_PLANES,
    DOMAIN,
    LOGGER,
)

type ForecastSolarConfigEntry = ConfigEntry[ForecastSolarDataUpdateCoordinator]


# TODO: Remove Plane after forecast_solar library is updated with native
# multi-plane support (see https://github.com/home-assistant-libs/forecast_solar/pull/275).
# Use `from forecast_solar import Plane` instead.
@dataclass
class Plane:
    """Configuration for a single plane.

    This mirrors the Plane dataclass that will be added to the forecast_solar library.
    """

    declination: float
    azimuth: float
    kwp: float


# TODO: Remove MultiPlaneForecastSolar after forecast_solar library is updated with native
# multi-plane support (see https://github.com/home-assistant-libs/forecast_solar/pull/275).
# The library's ForecastSolar class will accept a `planes` parameter directly.
@dataclass
class MultiPlaneForecastSolar(ForecastSolar):
    """Extended ForecastSolar client with multi-plane support.

    This is a temporary implementation until the forecast_solar library
    natively supports multiple planes via the `planes` parameter.
    """

    planes: list[Plane] = field(default_factory=list)

    async def estimate(self, actual: float = 0) -> Estimate:
        """Get solar production estimations from the Forecast.Solar API.

        Override to support multiple planes in the URL.
        """
        params = {"time": "utc", "damping": str(self.damping)}
        if self.inverter is not None:
            params["inverter"] = str(self.inverter)
        if self.horizon is not None:
            params["horizon"] = str(self.horizon)
        if self.damping_morning is not None and self.damping_evening is not None:
            params["damping_morning"] = str(self.damping_morning)
            params["damping_evening"] = str(self.damping_evening)
        if self.api_key is not None:
            params["actual"] = str(actual)

        # Build the plane path: /dec1/az1/kwp1/dec2/az2/kwp2/...
        plane_path = f"{self.declination}/{self.azimuth}/{self.kwp}"
        # Only include additional planes if an API key is provided
        if self.planes and self.api_key is not None:
            for plane in self.planes:
                plane_path += f"/{plane.declination}/{plane.azimuth}/{plane.kwp}"

        data = await self._request(
            f"estimate/{self.latitude}/{self.longitude}/{plane_path}",
            params=params,
        )

        return Estimate.from_dict(data)


class ForecastSolarDataUpdateCoordinator(DataUpdateCoordinator[Estimate]):
    """The Forecast.Solar Data Update Coordinator."""

    config_entry: ForecastSolarConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ForecastSolarConfigEntry) -> None:
        """Initialize the Forecast.Solar coordinator."""

        # Our option flow may cause it to be an empty string,
        # this if statement is here to catch that.
        api_key = entry.options.get(CONF_API_KEY) or None

        if (
            inverter_size := entry.options.get(CONF_INVERTER_SIZE)
        ) is not None and inverter_size > 0:
            inverter_size = inverter_size / 1000

        # Build the list of planes
        planes: list[Plane] = []

        # Add additional planes if configured
        additional_planes = entry.options.get(CONF_PLANES, [])
        for plane_config in additional_planes:
            plane = Plane(
                declination=plane_config[CONF_DECLINATION],
                azimuth=(plane_config[CONF_AZIMUTH] - 180),
                kwp=(plane_config[CONF_MODULES_POWER] / 1000),
            )
            planes.append(plane)

        # TODO: After forecast_solar library is updated with native multi-plane support
        # (see https://github.com/home-assistant-libs/forecast_solar/pull/275),
        # replace this block with a single ForecastSolar instantiation.
        self.forecast: ForecastSolar = MultiPlaneForecastSolar(
            api_key=api_key,
            session=async_get_clientsession(hass),
            latitude=entry.data[CONF_LATITUDE],
            longitude=entry.data[CONF_LONGITUDE],
            declination=entry.options[CONF_DECLINATION],
            azimuth=(entry.options[CONF_AZIMUTH] - 180),
            kwp=(entry.options[CONF_MODULES_POWER] / 1000),
            damping_morning=entry.options.get(CONF_DAMPING_MORNING, 0.0),
            damping_evening=entry.options.get(CONF_DAMPING_EVENING, 0.0),
            inverter=inverter_size,
            planes=planes,
        )

        # Free account have a resolution of 1 hour, using that as the default
        # update interval. Using a higher value for accounts with an API key.
        update_interval = timedelta(hours=1)
        if api_key is not None:
            update_interval = timedelta(minutes=30)

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
