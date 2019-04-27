"""
Train information for departures and delays, provided by Trafikverket.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.trafikverket_train/
"""

from datetime import date, datetime, timedelta
import asyncio
import logging
import voluptuous as vol


from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import (async_get_clientsession)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_TRAINS = "trains"
CONF_FROM = "from"
CONF_TO = "to"
CONF_TIME = "time"

ATTR_CANCELED = "canceled"
ATTR_DELAY_TIME = "number_of_minutes_delayed"
ATTR_PLANNED_TIME = "planned_time"  # Planned to arrive if no delays occur
ATTR_ESTIMATED_TIME = "estimated_time"  # ETA to arrive when delays occur
ATTR_ACTUAL_TIME = "actual_time"  # When it did arrive
ATTR_OTHER_INFORMATION = "other_information"
ATTR_DEVIATIONS = "deviations"

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TRAINS): [{
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Optional(CONF_TIME): cv.time}]
})


@asyncio.coroutine
def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the departure sensor."""
    _LOGGER.debug("Start async_setup_platform")
    from pytrafikverket import TrafikverketTrain
    httpsession = async_get_clientsession(hass)
    train_api = TrafikverketTrain(httpsession, config.get(CONF_API_KEY))
    sensors = []
    for train in config.get(CONF_TRAINS):
        from_sig = yield from train_api.async_get_train_station(
            train.get(CONF_FROM))
        to_sig = yield from train_api.async_get_train_station(
            train.get(CONF_TO))
        sensor = TrainSensor(train_api,
                             train.get(CONF_NAME),
                             from_sig,
                             to_sig,
                             train.get(CONF_TIME))
        sensors.append(sensor)

    async_add_devices(sensors, update_before_add=True)
    _LOGGER.debug("end async_setup_platform")


class TrainSensor(Entity):
    """Contains data about a train depature."""

    def __init__(self, train_api, name, from_sig, to_sig, time):
        """Initialize the sensor."""
        self._train_api = train_api
        self._name = name
        self._from_sig = from_sig
        self._to_sig = to_sig
        self._time = time
        self._state = None

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("start async_update")
        if self._time is not None:
            when = datetime.combine(date.today(), self._time)
            _LOGGER.debug("self._from_sig: %s, self._to_sig: %s, when: %s",
                          self._from_sig.name, self._to_sig.name, when)
            self._state = yield from \
                self._train_api.async_get_train_stop(
                    self._from_sig, self._to_sig, when)
        else:
            when = datetime.now()
            _LOGGER.debug("self._from_sig: %s, self._to_sig: %s, when: %s",
                          self._from_sig.name, self._to_sig.name, when)
            self._state = yield from \
                self._train_api.async_get_next_train_stop(
                    self._from_sig, self._to_sig, when)
        _LOGGER.debug("end async_update")

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state is None:
            return None
        state = self._state
        other_information = None
        if state.other_information is not None and state.other_information:
            other_information = ", ".join(state.other_information)
        deviations = None
        if state.deviations is not None and state.deviations:
            deviations = ", ".join(state.deviations)
        delay_in_minutes = state.get_delay_time()
        if delay_in_minutes is not None:
            delay_in_minutes = delay_in_minutes.total_seconds() / 60
        return {ATTR_CANCELED: state.canceled,
                ATTR_DELAY_TIME: delay_in_minutes,
                ATTR_PLANNED_TIME: state.advertised_time_at_location,
                ATTR_ESTIMATED_TIME: state.estimated_time_at_location,
                ATTR_ACTUAL_TIME: state.time_at_location,
                ATTR_OTHER_INFORMATION: other_information,
                ATTR_DEVIATIONS: deviations}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the departure state."""
        if self._state is None:
            return None
        return self._state.get_state().name
