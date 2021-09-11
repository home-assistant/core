"""Support for ZoneMinder sensors."""
from __future__ import annotations

import logging

import voluptuous as vol
from zoneminder.monitor import TimePeriod

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as ZONEMINDER_DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE_ARCHIVED = "include_archived"

DEFAULT_INCLUDE_ARCHIVED = False

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="all",
        name="Events",
    ),
    SensorEntityDescription(
        key="hour",
        name="Events Last Hour",
    ),
    SensorEntityDescription(
        key="day",
        name="Events Last Day",
    ),
    SensorEntityDescription(
        key="week",
        name="Events Last Week",
    ),
    SensorEntityDescription(
        key="month",
        name="Events Last Month",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_INCLUDE_ARCHIVED, default=DEFAULT_INCLUDE_ARCHIVED
        ): cv.boolean,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["all"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder sensor platform."""
    include_archived = config[CONF_INCLUDE_ARCHIVED]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    sensors = []
    for zm_client in hass.data[ZONEMINDER_DOMAIN].values():
        monitors = zm_client.get_monitors()
        if not monitors:
            _LOGGER.warning("Could not fetch any monitors from ZoneMinder")

        for monitor in monitors:
            sensors.append(ZMSensorMonitors(monitor))

            sensors.extend(
                [
                    ZMSensorEvents(monitor, include_archived, description)
                    for description in SENSOR_TYPES
                    if description.key in monitored_conditions
                ]
            )

        sensors.append(ZMSensorRunState(zm_client))
    add_entities(sensors)


class ZMSensorMonitors(SensorEntity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor):
        """Initialize monitor sensor."""
        self._monitor = monitor
        self._state = None
        self._is_available = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._monitor.name} Status"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if Monitor is available."""
        return self._is_available

    def update(self):
        """Update the sensor."""
        state = self._monitor.function
        if not state:
            self._state = None
        else:
            self._state = state.value
        self._is_available = self._monitor.is_available


class ZMSensorEvents(SensorEntity):
    """Get the number of events for each monitor."""

    _attr_native_unit_of_measurement = "Events"

    def __init__(self, monitor, include_archived, description: SensorEntityDescription):
        """Initialize event sensor."""
        self.entity_description = description

        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = TimePeriod.get_time_period(description.key)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._monitor.name} {self.time_period.title}"

    def update(self):
        """Update the sensor."""
        self._attr_native_value = self._monitor.get_events(
            self.time_period, self._include_archived
        )


class ZMSensorRunState(SensorEntity):
    """Get the ZoneMinder run state."""

    def __init__(self, client):
        """Initialize run state sensor."""
        self._state = None
        self._is_available = None
        self._client = client

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Run State"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if ZoneMinder is available."""
        return self._is_available

    def update(self):
        """Update the sensor."""
        self._state = self._client.get_active_state()
        self._is_available = self._client.is_available
