"""
Component to offer a way to select a date and / or a time.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_datetime/
"""
import logging
import datetime

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ICON, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
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


def has_date_or_time(conf):
    """Check at least date or time is true."""
    if conf[CONF_HAS_DATE] or conf[CONF_HAS_TIME]:
        return conf

    raise vol.Invalid('Entity needs at least a date or a time')


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_HAS_DATE, default=False): cv.boolean,
            vol.Optional(CONF_HAS_TIME, default=False): cv.boolean,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_INITIAL): cv.string,
        }, has_date_or_time)})
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
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

    async def async_set_datetime_service(entity, call):
        """Handle a call to the input datetime 'set datetime' service."""
        time = call.data.get(ATTR_TIME)
        date = call.data.get(ATTR_DATE)
        if (entity.has_date and not date) or (entity.has_time and not time):
            _LOGGER.error("Invalid service data for %s "
                          "input_datetime.set_datetime: %s",
                          entity.entity_id, str(call.data))
            return

        entity.async_set_datetime(date, time)

    component.async_register_entity_service(
        SERVICE_SET_DATETIME, SERVICE_SET_DATETIME_SCHEMA,
        async_set_datetime_service
    )

    await component.async_add_entities(entities)
    return True


class InputDatetime(RestoreEntity):
    """Representation of a datetime input."""

    def __init__(self, object_id, name, has_date, has_time, icon, initial):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self.has_date = has_date
        self.has_time = has_time
        self._icon = icon
        self._initial = initial
        self._current_datetime = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        restore_val = None

        # Priority 1: Initial State
        if self._initial is not None:
            restore_val = self._initial

        # Priority 2: Old state
        if restore_val is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                restore_val = old_state.state

        if restore_val is not None:
            if not self.has_date:
                self._current_datetime = dt_util.parse_time(restore_val)
            elif not self.has_time:
                self._current_datetime = dt_util.parse_date(restore_val)
            else:
                self._current_datetime = dt_util.parse_datetime(restore_val)

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
        return self._current_datetime

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {
            'has_date': self.has_date,
            'has_time': self.has_time,
        }

        if self._current_datetime is None:
            return attrs

        if self.has_date and self._current_datetime is not None:
            attrs['year'] = self._current_datetime.year
            attrs['month'] = self._current_datetime.month
            attrs['day'] = self._current_datetime.day

        if self.has_time and self._current_datetime is not None:
            attrs['hour'] = self._current_datetime.hour
            attrs['minute'] = self._current_datetime.minute
            attrs['second'] = self._current_datetime.second

        if not self.has_date:
            attrs['timestamp'] = self._current_datetime.hour * 3600 + \
                                    self._current_datetime.minute * 60 + \
                                    self._current_datetime.second
        elif not self.has_time:
            extended = datetime.datetime.combine(self._current_datetime,
                                                 datetime.time(0, 0))
            attrs['timestamp'] = extended.timestamp()
        else:
            attrs['timestamp'] = self._current_datetime.timestamp()

        return attrs

    def async_set_datetime(self, date_val, time_val):
        """Set a new date / time."""
        if self.has_date and self.has_time and date_val and time_val:
            self._current_datetime = datetime.datetime.combine(date_val,
                                                               time_val)
        elif self.has_date and not self.has_time and date_val:
            self._current_datetime = date_val
        if self.has_time and not self.has_date and time_val:
            self._current_datetime = time_val

        self.async_schedule_update_ha_state()
