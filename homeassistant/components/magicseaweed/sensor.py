"""Support for magicseaweed data from magicseaweed.com."""
from __future__ import annotations

from datetime import timedelta
import logging

import magicseaweed
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

_LOGGER = logging.getLogger(__name__)

CONF_HOURS = "hours"
CONF_SPOT_ID = "spot_id"
CONF_UNITS = "units"

DEFAULT_UNIT = "us"
DEFAULT_NAME = "MSW"

ICON = "mdi:waves"

HOURS = ["12AM", "3AM", "6AM", "9AM", "12PM", "3PM", "6PM", "9PM"]

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="max_breaking_swell",
        name="Max",
    ),
    SensorEntityDescription(
        key="min_breaking_swell",
        name="Min",
    ),
    SensorEntityDescription(
        key="swell_forecast",
        name="Forecast",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


UNITS = ["eu", "uk", "us"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SPOT_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOURS, default=None): vol.All(
            cv.ensure_list, [vol.In(HOURS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNITS): vol.In(UNITS),
    }
)

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Magicseaweed sensor."""
    create_issue(
        hass,
        "magicseaweed",
        "pending_removal",
        breaks_in_ha_version="2023.3.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="pending_removal",
    )
    _LOGGER.warning(
        "The Magicseaweed integration is deprecated"
        " and will be removed in Home Assistant 2023.3"
    )

    name = config.get(CONF_NAME)
    spot_id = config[CONF_SPOT_ID]
    api_key = config[CONF_API_KEY]
    hours = config.get(CONF_HOURS)

    if CONF_UNITS in config:
        units = config.get(CONF_UNITS)
    elif hass.config.units is METRIC_SYSTEM:
        units = UNITS[0]
    else:
        units = UNITS[2]

    forecast_data = MagicSeaweedData(api_key=api_key, spot_id=spot_id, units=units)
    forecast_data.update()

    # If connection failed don't setup platform.
    if forecast_data.currently is None or forecast_data.hourly is None:
        return

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    sensors = [
        MagicSeaweedSensor(forecast_data, name, units, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]
    if hours is not None:
        sensors.extend(
            [
                MagicSeaweedSensor(forecast_data, name, units, description, hour)
                for description in SENSOR_TYPES
                if description.key in monitored_conditions
                and "forecast" not in description.key
                for hour in hours
            ]
        )
    add_entities(sensors, True)


class MagicSeaweedSensor(SensorEntity):
    """Implementation of a MagicSeaweed sensor."""

    _attr_attribution = "Data provided by magicseaweed.com"
    _attr_icon = ICON

    def __init__(
        self,
        forecast_data,
        name,
        unit_system,
        description: SensorEntityDescription,
        hour=None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.client_name = name
        self.data = forecast_data
        self.hour = hour
        self._unit_system = unit_system

        if hour is None and "forecast" in description.key:
            self._attr_name = f"{name} {description.name}"
        elif hour is None:
            self._attr_name = f"Current {name} {description.name}"
        else:
            self._attr_name = f"{hour} {name} {description.name}"

        self._attr_extra_state_attributes = {}

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self._unit_system

    def update(self) -> None:
        """Get the latest data from Magicseaweed and updates the states."""
        self.data.update()
        if self.hour is None:
            forecast = self.data.currently
        else:
            forecast = self.data.hourly[self.hour]

        self._attr_native_unit_of_measurement = forecast.swell_unit
        sensor_type = self.entity_description.key
        if sensor_type == "min_breaking_swell":
            self._attr_native_value = forecast.swell_minBreakingHeight
        elif sensor_type == "max_breaking_swell":
            self._attr_native_value = forecast.swell_maxBreakingHeight
        elif sensor_type == "swell_forecast":
            summary = (
                f"{forecast.swell_minBreakingHeight} -"
                f" {forecast.swell_maxBreakingHeight}"
            )
            self._attr_native_value = summary
            if self.hour is None:
                for hour, data in self.data.hourly.items():
                    occurs = hour
                    hr_summary = (
                        f"{data.swell_minBreakingHeight} -"
                        f" {data.swell_maxBreakingHeight} {data.swell_unit}"
                    )
                    self._attr_extra_state_attributes[occurs] = hr_summary

        if sensor_type != "swell_forecast":
            self._attr_extra_state_attributes.update(forecast.attrs)


class MagicSeaweedData:
    """Get the latest data from MagicSeaweed."""

    def __init__(self, api_key, spot_id, units):
        """Initialize the data object."""
        self._msw = magicseaweed.MSW_Forecast(api_key, spot_id, None, units)
        self.currently = None
        self.hourly = {}

        # Apply throttling to methods using configured interval
        self.update = Throttle(MIN_TIME_BETWEEN_UPDATES)(self._update)

    def _update(self):
        """Get the latest data from MagicSeaweed."""
        try:
            forecasts = self._msw.get_future()
            self.currently = forecasts.data[0]
            for forecast in forecasts.data[:8]:
                hour = dt_util.utc_from_timestamp(forecast.localTimestamp).strftime(
                    "%-I%p"
                )
                self.hourly[hour] = forecast
        except ConnectionError:
            _LOGGER.error("Unable to retrieve data from Magicseaweed")
