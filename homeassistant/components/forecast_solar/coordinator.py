"""DataUpdateCoordinator for the Forecast.Solar integration."""
from __future__ import annotations

from datetime import timedelta

from forecast_solar import Estimate, ForecastSolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_HOME_LOCATION,
    CONF_INVERTER_SIZE,
    CONF_LOCATION_ZONE,
    CONF_MODULES_POWER,
    DOMAIN,
    LOGGER,
)


class ForecastSolarDataUpdateCoordinator(DataUpdateCoordinator[Estimate]):
    """The Forecast.Solar Data Update Coordinator."""

    async def retry_setup(self, now=None):
        """Retry setup if zone is not yet available."""
        await self.async_config_entry_first_refresh()

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Forecast.Solar coordinator."""
        self.config_entry = entry

        # Our option flow may cause it to be an empty string,
        # this if statement is here to catch that.
        api_key = entry.options.get(CONF_API_KEY) or None

        if (
            inverter_size := entry.options.get(CONF_INVERTER_SIZE)
        ) is not None and inverter_size > 0:
            inverter_size = inverter_size / 1000
        if entry.data.get(CONF_HOME_LOCATION):
            latitude = hass.config.latitude
            longitude = hass.config.longitude
        elif entry.data.get(CONF_LOCATION_ZONE):
            zone = hass.states.get(entry.data.get(CONF_LOCATION_ZONE))
            if (
                zone is None
                or "latitude" not in zone.attributes
                or "longitude" not in zone.attributes
            ):
                LOGGER.debug(
                    "Zone entity not yet available or missing latitude/longitude attributes."
                )
                async_call_later(hass, 10, self.retry_setup)
                return False
            latitude = zone.attributes["latitude"]
            longitude = zone.attributes["longitude"]
        else:
            latitude = entry.data[CONF_LATITUDE]
            longitude = entry.data[CONF_LONGITUDE]
        self.sensors_unavailable = False
        if entry.options.get(CONF_DECLINATION_SENSOR):
            declination_sensor = hass.states.get(
                entry.options.get(CONF_DECLINATION_SENSOR)
            )
            if (
                declination_sensor is None
                or declination_sensor.state in ["unavailable", "unknown", None]
                or not declination_sensor.state.replace(".", "", 1).isdigit()
            ):
                LOGGER.debug(
                    "Sensor %s not available or in 'unavailable' state",
                    entry.options.get(CONF_DECLINATION_SENSOR),
                )
                declination = 0
                self.sensors_unavailable = True
            else:
                declination = float(declination_sensor.state)
                if declination < 0 or declination > 90:
                    LOGGER.debug(
                        "Invalid declination value: %.3f.. Expected value between 0 and 90.",
                        declination,
                    )
                    self.sensors_unavailable = True
        else:
            declination = entry.options[CONF_DECLINATION]
        if entry.options.get(CONF_AZIMUTH_SENSOR):
            azimuth_sensor = hass.states.get(entry.options.get(CONF_AZIMUTH_SENSOR))
            if (
                azimuth_sensor is None
                or azimuth_sensor.state in ["unavailable", "unknown", None]
                or not azimuth_sensor.state.replace(".", "", 1).isdigit()
            ):
                LOGGER.debug(
                    "Sensor %s not available or in 'unavailable' state.",
                    entry.options.get(CONF_AZIMUTH_SENSOR),
                )
                azimuth = 0
                self.sensors_unavailable = True
            else:
                azimuth = float(azimuth_sensor.state) - 180
                if azimuth < -180 or azimuth > 180:
                    LOGGER.debug(
                        "Invalid azimuth value: %.3f. Expected value between 0 and 360.",
                        azimuth + 180,
                    )
                    self.sensors_unavailable = True
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

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> Estimate:
        """Fetch Forecast.Solar estimates."""
        # Check if the required sensors are unavailable or have invalid values.
        if self.sensors_unavailable:
            raise UpdateFailed(
                "Required sensors are unavailable or have invalid values."
            )
        return await self.forecast.estimate()
