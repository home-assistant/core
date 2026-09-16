"""DataUpdateCoordinator for the Forecast.Solar integration."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, override

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


def _resolve_location(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> tuple[float, float]:
    """Resolve the forecast location from config, falling back to HA's home location."""
    if CONF_LATITUDE in data:
        return data[CONF_LATITUDE], data[CONF_LONGITUDE]
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
        api_key = entry.options.get(CONF_API_KEY) or None

        # Free account have a resolution of 1 hour, using that as the default
        # update interval. Using a higher value for accounts with an API key.
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=30)
            if api_key is not None
            else timedelta(hours=1),
        )

        if (
            inverter_size := entry.options.get(CONF_INVERTER_SIZE)
        ) is not None and inverter_size > 0:
            inverter_size = inverter_size / 1000

        main_plane, *extra_planes = entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)

        # Errors collected here are reported by the first refresh, which re-resolves.
        errors: list[str] = []
        declination, azimuth = self._plane_angles(main_plane.data, errors)
        latitude, longitude = _resolve_location(hass, entry.data)

        self.planes = []
        for subentry in extra_planes:
            plane_declination, plane_azimuth = self._plane_angles(subentry.data, errors)
            self.planes.append(
                Plane(
                    declination=plane_declination,
                    azimuth=plane_azimuth,
                    kwp=(subentry.data[CONF_MODULES_POWER] / 1000),
                )
            )

        self.forecast = ForecastSolar(
            api_key=api_key,
            session=async_get_clientsession(hass),
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

    def _get_safe_sensor_value(
        self,
        entity_id: str,
        min_value: float,
        max_value: float,
        name: str,
        errors: list[str],
    ) -> float:
        """Fetch and validate a numeric sensor value. Returns 0.0 on failure."""
        sensor = self.hass.states.get(entity_id)
        error: str | None = None

        if sensor is None:
            error = f"{name} sensor '{entity_id}' not available"
        else:
            state = sensor.state
            if state in ("unavailable", "unknown"):
                error = f"{name} sensor '{entity_id}' invalid state: {state}"
            else:
                try:
                    value = float(state)
                except TypeError, ValueError:
                    error = f"{name} sensor '{entity_id}' not a number: {state}"
                else:
                    if not (min_value <= value <= max_value):
                        error = (
                            f"{name} sensor '{entity_id}' value {value:.3f} "
                            f"out of range [{min_value}, {max_value}]"
                        )
                    else:
                        return value

        LOGGER.debug(error)
        errors.append(error)
        return 0.0

    def _resolve_angle(
        self,
        data: Mapping[str, Any],
        value_key: str,
        sensor_key: str,
        min_value: float,
        max_value: float,
        name: str,
        errors: list[str],
    ) -> float:
        """Resolve a plane angle from its fixed value or a sensor."""
        if entity_id := data.get(sensor_key):
            return self._get_safe_sensor_value(
                entity_id, min_value, max_value, name, errors
            )
        return float(data[value_key])

    def _plane_angles(
        self, data: Mapping[str, Any], errors: list[str]
    ) -> tuple[float, float]:
        """Resolve a plane's declination and azimuth from fixed values or sensors.

        UI stores azimuth 0-360 (0=North); the API expects -180..180 (0=South).
        """
        declination = self._resolve_angle(
            data,
            CONF_DECLINATION,
            CONF_DECLINATION_SENSOR,
            0,
            90,
            "Declination",
            errors,
        )
        azimuth = self._resolve_angle(
            data, CONF_AZIMUTH, CONF_AZIMUTH_SENSOR, 0, 360, "Azimuth", errors
        )
        return declination, azimuth - 180

    def _refresh_plane_angles(self) -> list[str]:
        """Re-resolve every plane's declination/azimuth, returning any errors."""
        errors: list[str] = []
        main_plane, *extra_planes = self.config_entry.get_subentries_of_type(
            SUBENTRY_TYPE_PLANE
        )

        self.forecast.declination, self.forecast.azimuth = self._plane_angles(
            main_plane.data, errors
        )
        for plane, subentry in zip(self.planes, extra_planes, strict=True):
            plane.declination, plane.azimuth = self._plane_angles(subentry.data, errors)

        return errors

    @override
    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        self.forecast.latitude, self.forecast.longitude = _resolve_location(
            self.hass, self.config_entry.data
        )
        if errors := self._refresh_plane_angles():
            raise UpdateFailed(f"Errors: {' '.join(sorted(errors))}")
        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
