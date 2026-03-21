"""DataUpdateCoordinator for the Forecast.Solar integration."""

from __future__ import annotations

from datetime import timedelta

from forecast_solar import Estimate, ForecastSolar, ForecastSolarConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AZIMUTH_MAX,
    AZIMUTH_MIN,
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DECLINATION_MAX,
    DECLINATION_MIN,
    DOMAIN,
    LOGGER,
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

        # location
        latitude = entry.options[CONF_LATITUDE]
        longitude = entry.options[CONF_LONGITUDE]

        # declination
        self._errors: set[str] = set()
        if declination_entry := entry.options.get(CONF_DECLINATION_SENSOR):
            declination = self._get_safe_sensor_value(
                hass, declination_entry, DECLINATION_MIN, DECLINATION_MAX, "Declination"
            )
        else:
            declination = entry.options[CONF_DECLINATION]

        # azimuth: UI stores 0-360 (0=North), API expects -180 to 180 (0=South)
        if azimuth_entry := entry.options.get(CONF_AZIMUTH_SENSOR):
            value = self._get_safe_sensor_value(
                hass, azimuth_entry, AZIMUTH_MIN, AZIMUTH_MAX, "Azimuth"
            )
            azimuth = value - 180 if value else 0.0
        else:
            azimuth = entry.options[CONF_AZIMUTH] - 180

        self.forecast = ForecastSolar(
            api_key=api_key,
            session=async_get_clientsession(hass),
            latitude=latitude,
            longitude=longitude,
            declination=declination,
            azimuth=azimuth,
            kwp=(entry.options[CONF_MODULES_POWER] / 1000),
            damping_morning=entry.options.get(CONF_DAMPING_MORNING, 0.0),
            damping_evening=entry.options.get(CONF_DAMPING_EVENING, 0.0),
            inverter=inverter_size,
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
            if state in ("unavailable", "unknown", None):
                error = f"{name} sensor '{entity_id}' invalid state: {state}"
            else:
                try:
                    value = float(state)
                except TypeError, ValueError:
                    error = f"{name} sensor '{entity_id}' not a number: {state}"
                else:
                    if not (min_value <= value <= max_value):
                        error = (
                            f"{name} sensor '{entity_id}' value {value:.3f} out of range "
                            f"[{min_value}, {max_value}]"
                        )
                    else:
                        return value

        LOGGER.debug(error)
        self._errors.add(error)
        return 0.0

    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        if self._errors:
            raise UpdateFailed(f"Errors: {' '.join(self._errors)}")
        try:
            return await self.forecast.estimate()
        except ForecastSolarConnectionError as error:
            raise UpdateFailed(error) from error
