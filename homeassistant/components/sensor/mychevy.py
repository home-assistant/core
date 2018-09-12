"""Support for MyChevy sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mychevy/
"""

import asyncio
import logging

from homeassistant.components.mychevy import (
    EVSensorConfig, DOMAIN as MYCHEVY_DOMAIN, MYCHEVY_ERROR, MYCHEVY_SUCCESS,
    NOTIFICATION_ID, NOTIFICATION_TITLE, UPDATE_TOPIC, ERROR_TOPIC
)
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import slugify

BATTERY_SENSOR = "batteryLevel"

SENSORS = [
    EVSensorConfig("Mileage", "totalMiles", "miles", "mdi:speedometer"),
    EVSensorConfig("Electric Range", "electricRange", "miles",
                   "mdi:speedometer"),
    EVSensorConfig("Charged By", "estimatedFullChargeBy"),
    EVSensorConfig("Charge Mode", "chargeMode"),
    EVSensorConfig("Battery Level", BATTERY_SENSOR, "%", "mdi:battery")
]

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the MyChevy sensors."""
    if discovery_info is None:
        return

    hub = hass.data[MYCHEVY_DOMAIN]
    sensors = [MyChevyStatus()]
    for sconfig in SENSORS:
        for car in hub.cars:
            sensors.append(EVSensor(hub, sconfig, car.vid))

    add_entities(sensors)


class MyChevyStatus(Entity):
    """A string representing the charge mode."""

    _name = "MyChevy Status"
    _icon = "mdi:car-connected"

    def __init__(self):
        """Initialize sensor with car connection."""
        self._state = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            UPDATE_TOPIC, self.success)

        self.hass.helpers.dispatcher.async_dispatcher_connect(
            ERROR_TOPIC, self.error)

    @callback
    def success(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_SUCCESS:
            _LOGGER.debug("Successfully connected to mychevy website")
            self._state = MYCHEVY_SUCCESS
        self.async_schedule_update_ha_state()

    @callback
    def error(self):
        """Update state, trigger updates."""
        if self._state != MYCHEVY_ERROR:
            self.hass.components.persistent_notification.create(
                "Error:<br/>Connection to mychevy website failed. "
                "This probably means the mychevy to OnStar link is down.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            self._state = MYCHEVY_ERROR
        self.async_schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False


class EVSensor(Entity):
    """Base EVSensor class.

    The only real difference between sensors is which units and what
    attribute from the car object they are returning. All logic can be
    built with just setting subclass attributes.

    """

    def __init__(self, connection, config, car_vid):
        """Initialize sensor with car connection."""
        self._conn = connection
        self._name = config.name
        self._attr = config.attr
        self._unit_of_measurement = config.unit_of_measurement
        self._icon = config.icon
        self._state = None
        self._car_vid = car_vid

        self.entity_id = ENTITY_ID_FORMAT.format(
            '{}_{}_{}'.format(MYCHEVY_DOMAIN,
                              slugify(self._car.name),
                              slugify(self._name)))

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            UPDATE_TOPIC, self.async_update_callback)

    @property
    def _car(self):
        """Return the car."""
        return self._conn.get_car(self._car_vid)

    @property
    def icon(self):
        """Return the icon."""
        if self._attr == BATTERY_SENSOR:
            return icon_for_battery_level(self.state)
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @callback
    def async_update_callback(self):
        """Update state."""
        if self._car is not None:
            self._state = getattr(self._car, self._attr, None)
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the state is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
