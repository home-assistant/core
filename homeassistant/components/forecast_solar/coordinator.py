"""DataUpdateCoordinator for the Forecast.Solar integration."""

from __future__ import annotations

from datetime import timedelta

from forecast_solar import Estimate, ForecastSolar, ForecastSolarConnectionError, Plane

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
    DEFAULT_DAMPING,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PLANE,
)

type ForecastSolarConfigEntry = ConfigEntry[ForecastSolarDataUpdateCoordinator]


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

        # Build the list of planes from subentries.
        plane_subentries = [
            subentry
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_PLANE
        ]

        self.forecast: ForecastSolar | None = None
        if plane_subentries and (
            len(plane_subentries) == 1 or api_key is not None
        ):
            # The first plane subentry is the main plane
            main_plane = plane_subentries[0]

            # Additional planes
            planes: list[Plane] = [
                Plane(
                    declination=subentry.data[CONF_DECLINATION],
                    azimuth=(subentry.data[CONF_AZIMUTH] - 180),
                    kwp=(subentry.data[CONF_MODULES_POWER] / 1000),
                )
                for subentry in plane_subentries[1:]
            ]

            self.forecast = ForecastSolar(
                api_key=api_key,
                session=async_get_clientsession(hass),
                latitude=entry.data[CONF_LATITUDE],
                longitude=entry.data[CONF_LONGITUDE],
                declination=main_plane.data[CONF_DECLINATION],
                azimuth=(main_plane.data[CONF_AZIMUTH] - 180),
                kwp=(main_plane.data[CONF_MODULES_POWER] / 1000),
                damping_morning=entry.options.get(
                    CONF_DAMPING_MORNING, DEFAULT_DAMPING
                ),
                damping_evening=entry.options.get(
                    CONF_DAMPING_EVENING, DEFAULT_DAMPING
                ),
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
        if not any(
            subentry.subentry_type == SUBENTRY_TYPE_PLANE
            for subentry in self.config_entry.subentries.values()
        ):
            raise UpdateFailed(
                "No plane configured, cannot set up Forecast.Solar"
            )

        if (
            len(self.config_entry.subentries) > 1
            and not self.config_entry.options.get(CONF_API_KEY)
        ):
            raise UpdateFailed(
                "An API key is required when more than one plane is configured"
            )

        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
