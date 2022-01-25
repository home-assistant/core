"""Support for getting weather alerts from NOAA and other alert sources, thanks to the help of OpenWeatherMap."""

import datetime
from datetime import timedelta
import logging

import pytz
import requests

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import API_ENDPOINT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""

    async def async_update_data():
        """Fetch data from OWM."""
        # Using a data update coordinator so we don't literally get rid of all our requests for the month >.>
        endpoint = API_ENDPOINT.format(
            lat=config_entry.data["lat"],
            lon=config_entry.data["lon"],
            api_key=config_entry.data["api_key"],
        )
        try:
            response = await hass.async_add_executor_job(requests.get, endpoint)
        except requests.exceptions.HTTPError as error:
            raise UpdateFailed(
                "Cannot connect to alerts API. Please try again later"
            ) from error
        except requests.exceptions.RequestException as error:
            raise UpdateFailed(
                "Cannot connect to alerts API. Please try again later"
            ) from error

        # check if it didn't return code 401
        if response.status_code == 401:
            _LOGGER.error("Invalid API key")
            raise ConfigEntryAuthFailed("Invalid API key")

        if response.status_code == 404:
            _LOGGER.error("Invalid location")
            raise ConfigEntryAuthFailed("Invalid location")

        if response.status_code == 429:
            _LOGGER.error("Too many requests")
            raise UpdateFailed("Too many requests")

        if (
            response.status_code == 500
            or response.status_code == 502
            or response.status_code == 503
            or response.status_code == 504
        ):
            _LOGGER.error("Service Unavailable")
            raise UpdateFailed("Service Unavailable")

        if response.status_code == 200:
            return response.json()
        else:
            raise UpdateFailed("Unknown error")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="nws_alerts",
        update_method=async_update_data,
        update_interval=timedelta(seconds=config_entry.data.get("update_interval")),
    )

    await coordinator.async_config_entry_first_refresh()
    sensor = WeatherAlertSensor(hass, config_entry, coordinator)
    async_add_entities([sensor])


class WeatherAlertSensor(CoordinatorEntity, SensorEntity):
    """Weather alert sensor."""
    
    _attr_attribution = (
        "Data provided by the OpenWeatherMap Organization\n"
        "© 2012 — 2021 OpenWeather ® All rights reserved"
        )
    _attr_icon = "mdi:alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
        

    def __init__(self, hass, config, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._attr_name = config.data.get("friendly_name", "NWS Alerts")
        self._alert_count = None
        self._attr_unique_id = (
            self._name
            + "-"
            + str(config.data["lat"])
            + "-"
            + str(config.data["lon"])
            + "-"
            + config.entry_id
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this sensor."""
        return self._unique_id

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the native value of the sensor."""
        if hasattr(self.coordinator.data, "alerts"):
            return len(self.coordinator.data["alerts"])
        else:
            return 0

    # the property below is the star of the show
    @property
    def extra_state_attributes(self) -> dict:
        """Return the messages of all the alerts."""
        # Convert the start and end times from unix UTC to Home Assistant's time zone and format
        # the alert message
        attrs = {}
        if self.coordinator.data is not None:
            alerts = self.coordinator.data.get("alerts")
            if alerts is not None:
                timezone = pytz.timezone(self.hass.config.time_zone)
                utc = pytz.utc
                fmt = "%Y-%m-%d %H:%M"
                alerts = [
                    {
                        "start": datetime.datetime.fromtimestamp(alert["start"], tz=utc)
                        .astimezone(timezone)
                        .strftime(fmt),
                        "end": datetime.datetime.fromtimestamp(alert["end"], tz=utc)
                        .astimezone(timezone)
                        .strftime(fmt),
                        "sender_name": alert.get("sender_name"),
                        "event": alert.get("event"),
                        "description": alert.get("description"),
                    }
                    for alert in alerts
                ]
                # we cannot have a list of dicts, we can only have strings and ints iirc
                # let's parse it so that both humans and machines can read it
                sender_name = " - ".join([alert.get("sender_name") for alert in alerts])
                event = " - ".join([alert.get("event") for alert in alerts])
                start = " - ".join([alert.get("start") for alert in alerts])
                end = " - ".join([alert.get("end") for alert in alerts])
                description = " - ".join([alert.get("description") for alert in alerts])
                attrs = {
                    "sender_name": sender_name,
                    "event": event,
                    "start": start,
                    "end": end,
                    "description": description,
                }

        return attrs

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Data provided by the OpenWeatherMap Organization\n© 2012 — 2021 OpenWeather ® All rights reserved"  # I don't want to get sued for this, but I can't find a way to get the attribution from the API

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:alert"
