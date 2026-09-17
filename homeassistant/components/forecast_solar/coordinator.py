"""DataUpdateCoordinator for the Forecast.Solar integration."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, cast, override

from forecast_solar import Estimate, ForecastSolar, ForecastSolarConnectionError, Plane

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DEFAULT_DAMPING,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PLANE,
)

type ForecastSolarConfigEntry = ConfigEntry[ForecastSolarDataUpdateCoordinator]


class SensorUpdateFailed(UpdateFailed):
    """Raised when a plane sensor can't be read, before the API is called."""


def _resolve_location(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> tuple[float, float]:
    """Resolve the forecast location from config, falling back to HA's home location."""
    if (latitude := data.get(CONF_LATITUDE)) is not None and (
        longitude := data.get(CONF_LONGITUDE)
    ) is not None:
        return latitude, longitude
    return hass.config.latitude, hass.config.longitude


class ForecastSolarDataUpdateCoordinator(DataUpdateCoordinator[Estimate]):
    """The Forecast.Solar Data Update Coordinator."""

    config_entry: ForecastSolarConfigEntry
    forecast: ForecastSolar
    planes: list[Plane]

    def __init__(self, hass: HomeAssistant, entry: ForecastSolarConfigEntry) -> None:
        """Initialize the Forecast.Solar coordinator."""
        # Our option flow may cause it to be an empty string,
        # this if statement is here to catch that.
        self._api_key = entry.options.get(CONF_API_KEY) or None

        # Free account have a resolution of 1 hour, using that as the default
        # update interval. Using a higher value for accounts with an API key.
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=30)
            if self._api_key is not None
            else timedelta(hours=1),
        )

    @override
    async def _async_setup(self) -> None:
        """Build the client; an unreadable sensor raises and retries the setup."""
        entry = self.config_entry
        if (
            inverter_size := entry.options.get(CONF_INVERTER_SIZE)
        ) is not None and inverter_size > 0:
            inverter_size = inverter_size / 1000

        main_plane, *extra_planes = entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)

        declination, azimuth = self._plane_angles(main_plane.data)
        latitude, longitude = _resolve_location(self.hass, entry.data)

        self.planes = []
        for subentry in extra_planes:
            plane_declination, plane_azimuth = self._plane_angles(subentry.data)
            self.planes.append(
                Plane(
                    declination=plane_declination,
                    azimuth=plane_azimuth,
                    kwp=(subentry.data[CONF_MODULES_POWER] / 1000),
                )
            )

        self.forecast = ForecastSolar(
            api_key=self._api_key,
            session=async_get_clientsession(self.hass),
            latitude=latitude,
            longitude=longitude,
            declination=declination,
            azimuth=azimuth,
            kwp=(main_plane.data[CONF_MODULES_POWER] / 1000),
            damping_morning=entry.options.get(CONF_DAMPING_MORNING, DEFAULT_DAMPING),
            damping_evening=entry.options.get(CONF_DAMPING_EVENING, DEFAULT_DAMPING),
            inverter=inverter_size,
            planes=self.planes,
        )

    def _sensor_value(
        self, entity_id: str, min_value: float, max_value: float
    ) -> float:
        """Return a sensor's numeric value, raising if it can't be used."""
        if (sensor := self.hass.states.get(entity_id)) is None:
            raise SensorUpdateFailed(
                translation_domain=DOMAIN,
                translation_key="sensor_not_found",
                translation_placeholders={"entity_id": entity_id},
            )

        try:
            value = float(sensor.state)
        except ValueError:
            value = None
        if value is None or not min_value <= value <= max_value:
            raise SensorUpdateFailed(
                translation_domain=DOMAIN,
                translation_key="sensor_invalid",
                translation_placeholders={
                    "entity_id": entity_id,
                    "state": sensor.state,
                    "min": str(min_value),
                    "max": str(max_value),
                },
            )
        return value

    def _resolve_angle(
        self,
        data: Mapping[str, Any],
        value_key: str,
        sensor_key: str,
        min_value: float,
        max_value: float,
    ) -> float:
        """Resolve a plane angle from its sensor if it has one, else its fixed value."""
        if (entity_id := data.get(sensor_key)) is not None:
            return self._sensor_value(entity_id, min_value, max_value)
        return cast(float, data[value_key])

    def _plane_angles(self, data: Mapping[str, Any]) -> tuple[float, float]:
        """Resolve a plane's declination and azimuth.

        UI stores azimuth 0-360 (0=North); the API expects -180..180 (0=South).
        A sensor may use any convention, e.g. a compass reporting -180..180,
        so its reading is normalised rather than rejected.
        """
        declination = self._resolve_angle(
            data, CONF_DECLINATION, CONF_DECLINATION_SENSOR, 0, 90
        )
        azimuth = self._resolve_angle(
            data, CONF_AZIMUTH, CONF_AZIMUTH_SENSOR, -360, 360
        )
        return declination, azimuth % 360 - 180

    def _refresh_plane_angles(self) -> None:
        """Re-resolve every plane's declination/azimuth from its sensors."""
        main_plane, *extra_planes = self.config_entry.get_subentries_of_type(
            SUBENTRY_TYPE_PLANE
        )

        self.forecast.declination, self.forecast.azimuth = self._plane_angles(
            main_plane.data
        )
        for plane, subentry in zip(self.planes, extra_planes, strict=True):
            plane.declination, plane.azimuth = self._plane_angles(subentry.data)

    @override
    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        self.forecast.latitude, self.forecast.longitude = _resolve_location(
            self.hass, self.config_entry.data
        )
        self._refresh_plane_angles()
        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
