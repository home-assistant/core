"""
Component to offer a way to select a date and / or a time.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_datetime/
"""
import asyncio
import logging
import datetime

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'input_datetime'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_HAS_DATE = 'has_date'
CONF_HAS_TIME = 'has_time'
CONF_INITIAL = 'initial'

ATTR_DATE = 'date'
ATTR_TIME = 'time'

SERVICE_SET_DATETIME = 'set_datetime'

SERVICE_SET_DATETIME_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DATE): cv.date,
    vol.Optional(ATTR_TIME): cv.time,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_HAS_DATE): cv.boolean,
            vol.Required(CONF_HAS_TIME): cv.boolean,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_INITIAL): cv.string,
        }, cv.has_at_least_one_key_value((CONF_HAS_DATE, True),
                                         (CONF_HAS_TIME, True)))})
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_set_datetime(hass, entity_id, dt_value):
    """Set date and / or time of input_datetime."""
    yield from hass.services.async_call(DOMAIN, SERVICE_SET_DATETIME, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_DATE: dt_value.date(),
        ATTR_TIME: dt_value.time()
    })


@asyncio.coroutine
def async_setup(hass, config):
    """Set up an input datetime."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        has_time = cfg.get(CONF_HAS_TIME)
        has_date = cfg.get(CONF_HAS_DATE)
        icon = cfg.get(CONF_ICON)
        initial = cfg.get(CONF_INITIAL)
        entities.append(InputDatetime(object_id, name,
                                      has_date, has_time, icon, initial))

    if not entities:
        return False

    @asyncio.coroutine
    def async_set_datetime_service(call):
        """Handle a call to the input datetime 'set datetime' service."""
        target_inputs = component.async_extract_from_service(call)

        tasks = []
        for input_datetime in target_inputs:
            time = call.data.get(ATTR_TIME)
            date = call.data.get(ATTR_DATE)
            if (input_datetime.has_date() and not date) or \
               (input_datetime.has_time() and not time):
                _LOGGER.error("Invalid service data for "
                              "input_datetime.set_datetime: %s",
                              str(call.data))
                continue

            tasks.append(input_datetime.async_set_datetime(date, time))

        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DATETIME, async_set_datetime_service,
        schema=SERVICE_SET_DATETIME_SCHEMA)

    yield from component.async_add_entities(entities)
    return True


class InputDatetime(Entity):
    """Representation of a datetime input."""

    def __init__(self, object_id, name, has_date, has_time, icon, initial):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._has_date = has_date
        self._has_time = has_time
        self._icon = icon
        self._initial = initial
        self._current_datetime = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Run when entity about to be added."""
        restore_val = None

        # Priority 1: Initial State
        if self._initial is not None:
            restore_val = self._initial

        # Priority 2: Old state
        if restore_val is None:
            old_state = yield from async_get_last_state(self.hass,
                                                        self.entity_id)
            if old_state is not None:
                restore_val = old_state.state

        if restore_val is not None:
            if not self._has_date:
                self._current_datetime = dt_util.parse_time(restore_val)
            elif not self._has_time:
                self._current_datetime = dt_util.parse_date(restore_val)
            else:
                self._current_datetime = dt_util.parse_datetime(restore_val)

    def has_date(self):
        """Return whether the input datetime carries a date."""
        return self._has_date

    def has_time(self):
        """Return whether the input datetime carries a time."""
        return self._has_time

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the select input."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the state of the component."""
        if self._current_datetime is None:
            return STATE_UNKNOWN

        return self._current_datetime

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {
            'has_date': self._has_date,
            'has_time': self._has_time,
        }

        if self._current_datetime is None:
            return attrs

        if self._has_date and self._current_datetime is not None:
            attrs['year'] = self._current_datetime.year
            attrs['month'] = self._current_datetime.month
            attrs['day'] = self._current_datetime.day

        if self._has_time and self._current_datetime is not None:
            attrs['hour'] = self._current_datetime.hour
            attrs['minute'] = self._current_datetime.minute
            attrs['second'] = self._current_datetime.second

        if self._current_datetime is not None:
            if not self._has_date:
                attrs['timestamp'] = self._current_datetime.hour * 3600 + \
                                     self._current_datetime.minute * 60 + \
                                     self._current_datetime.second
            elif not self._has_time:
                extended = datetime.datetime.combine(self._current_datetime,
                                                     datetime.time(0, 0))
                attrs['timestamp'] = extended.timestamp()
            else:
                attrs['timestamp'] = self._current_datetime.timestamp()

        return attrs

    @asyncio.coroutine
    def async_set_datetime(self, date_val, time_val):
        """Set a new date / time."""
        if self._has_date and self._has_time and date_val and time_val:
            self._current_datetime = datetime.datetime.combine(date_val,
                                                               time_val)
        elif self._has_date and not self._has_time and date_val:
            self._current_datetime = date_val
        if self._has_time and not self._has_date and time_val:
            self._current_datetime = time_val

        yield from self.async_update_ha_state()
