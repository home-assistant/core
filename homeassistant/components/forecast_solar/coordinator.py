"""DataUpdateCoordinator for the Forecast.Solar integration."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, override

from forecast_solar import Estimate, ForecastSolar, ForecastSolarConnectionError, Plane

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
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

    def __init__(self, hass: HomeAssistant, entry: ForecastSolarConfigEntry) -> None:
        """Initialize the Forecast.Solar coordinator."""
        self._errors: set[str] = set()

        # Our option flow may cause it to be an empty string,
        # this if statement is here to catch that.
        api_key = entry.options.get(CONF_API_KEY) or None

        if (
            inverter_size := entry.options.get(CONF_INVERTER_SIZE)
        ) is not None and inverter_size > 0:
            inverter_size = inverter_size / 1000

        self._plane_subentries: list[ConfigSubentry] = entry.get_subentries_of_type(
            SUBENTRY_TYPE_PLANE
        )
        main_plane, *extra_planes = self._plane_subentries

        # Real angle values are resolved by _refresh_plane_angles() below;
        # 0.0 here is just a placeholder to construct the dataclasses with.
        planes: list[Plane] = [
            Plane(
                declination=0.0,
                azimuth=0.0,
                kwp=(subentry.data[CONF_MODULES_POWER] / 1000),
            )
            for subentry in extra_planes
        ]

        latitude, longitude = _resolve_location(hass, entry.data)

        self.forecast = ForecastSolar(
            api_key=api_key,
            session=async_get_clientsession(hass),
            latitude=latitude,
            longitude=longitude,
            declination=0.0,
            azimuth=0.0,
            kwp=(main_plane.data[CONF_MODULES_POWER] / 1000),
            damping_morning=entry.options.get(CONF_DAMPING_MORNING, DEFAULT_DAMPING),
            damping_evening=entry.options.get(CONF_DAMPING_EVENING, DEFAULT_DAMPING),
            inverter=inverter_size,
            planes=planes,
        )
        self._refresh_plane_angles(hass)

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

    def _get_safe_sensor_value(
        self,
        hass: HomeAssistant,
        entity_id: str,
        min_value: float,
        max_value: float,
        name: str,
    ) -> float:
        """Fetch and validate a numeric sensor value. Returns 0.0 on failure."""
        sensor = hass.states.get(entity_id)
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
        self._errors.add(error)
        return 0.0

    def _resolve_angle(
        self,
        hass: HomeAssistant,
        data: Mapping[str, Any],
        value_key: str,
        sensor_key: str,
        min_value: float,
        max_value: float,
        name: str,
    ) -> float:
        """Resolve a plane angle from its fixed value or a sensor."""
        if entity_id := data.get(sensor_key):
            return self._get_safe_sensor_value(
                hass, entity_id, min_value, max_value, name
            )
        return float(data[value_key])

    def _refresh_plane_angles(self, hass: HomeAssistant) -> None:
        """Re-resolve every plane's declination/azimuth from live sensors.

        UI stores azimuth 0-360 (0=North); the API expects -180..180 (0=South).
        """
        self._errors = set()
        main_plane, *extra_planes = self._plane_subentries

        self.forecast.declination = self._resolve_angle(
            hass,
            main_plane.data,
            CONF_DECLINATION,
            CONF_DECLINATION_SENSOR,
            0,
            90,
            "Declination",
        )
        self.forecast.azimuth = (
            self._resolve_angle(
                hass,
                main_plane.data,
                CONF_AZIMUTH,
                CONF_AZIMUTH_SENSOR,
                0,
                360,
                "Azimuth",
            )
            - 180
        )

        for plane, subentry in zip(
            self.forecast.planes or [], extra_planes, strict=True
        ):
            plane.declination = self._resolve_angle(
                hass,
                subentry.data,
                CONF_DECLINATION,
                CONF_DECLINATION_SENSOR,
                0,
                90,
                "Declination",
            )
            plane.azimuth = (
                self._resolve_angle(
                    hass,
                    subentry.data,
                    CONF_AZIMUTH,
                    CONF_AZIMUTH_SENSOR,
                    0,
                    360,
                    "Azimuth",
                )
                - 180
            )

    @override
    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        self.forecast.latitude, self.forecast.longitude = _resolve_location(
            self.hass, self.config_entry.data
        )
        self._refresh_plane_angles(self.hass)
        if self._errors:
            raise UpdateFailed(f"Errors: {' '.join(sorted(self._errors))}")
        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
