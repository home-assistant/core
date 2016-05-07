"""Offer reusable conditions."""
from datetime import timedelta
import logging
import sys

from homeassistant.components import (
    zone as zone_cmp, sun as sun_cmp)
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE,
    CONF_ENTITY_ID, CONF_VALUE_TEMPLATE, CONF_CONDITION,
    WEEKDAYS, CONF_STATE, CONF_ZONE, CONF_BEFORE,
    CONF_AFTER, CONF_WEEKDAY, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET,
    CONF_BELOW, CONF_ABOVE)
from homeassistant.exceptions import TemplateError, HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import render
import homeassistant.util.dt as dt_util

FROM_CONFIG_FORMAT = '{}_from_config'

_LOGGER = logging.getLogger(__name__)


def from_config(config, config_validation=True):
    """Turn a condition configuration into a method."""
    factory = getattr(
        sys.modules[__name__],
        FROM_CONFIG_FORMAT.format(config.get(CONF_CONDITION)), None)

    if factory is None:
        raise HomeAssistantError('Invalid condition "{}" specified {}'.format(
            config.get(CONF_CONDITION), config))

    return factory(config, config_validation)


def and_from_config(config, config_validation=True):
    """Create multi condition matcher using 'AND'."""
    if config_validation:
        config = cv.AND_CONDITION_SCHEMA(config)
    checks = [from_config(entry) for entry in config['conditions']]

    def if_and_condition(hass, variables=None):
        """Test and condition."""
        for check in checks:
            try:
                if not check(hass, variables):
                    return False
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.warning('Error during and-condition: %s', ex)
                return False

        return True

    return if_and_condition


def or_from_config(config, config_validation=True):
    """Create multi condition matcher using 'OR'."""
    if config_validation:
        config = cv.OR_CONDITION_SCHEMA(config)
    checks = [from_config(entry) for entry in config['conditions']]

    def if_or_condition(hass, variables=None):
        """Test and condition."""
        for check in checks:
            try:
                if check(hass, variables):
                    return True
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.warning('Error during or-condition: %s', ex)

        return False

    return if_or_condition


# pylint: disable=too-many-arguments
def numeric_state(hass, entity, below=None, above=None, value_template=None,
                  variables=None):
    """Test a numeric state condition."""
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    if value_template is None:
        value = entity.state
    else:
        variables = dict(variables or {})
        variables['state'] = entity
        try:
            value = render(hass, value_template, variables)
        except TemplateError as ex:
            _LOGGER.error(ex)
            return False

    try:
        value = float(value)
    except ValueError:
        _LOGGER.warning("Value cannot be processed as a number: %s", value)
        return False

    if below is not None and value > below:
        return False

    if above is not None and value < above:
        return False

    return True


def numeric_state_from_config(config, config_validation=True):
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.NUMERIC_STATE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def if_numeric_state(hass, variables=None):
        """Test numeric state condition."""
        return numeric_state(hass, entity_id, below, above, value_template,
                             variables)

    return if_numeric_state


def state(hass, entity, req_state, for_period=None):
    """Test if state matches requirements."""
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    is_state = entity.state == req_state

    if for_period is None or not is_state:
        return is_state

    return dt_util.utcnow() - for_period > entity.last_changed


def state_from_config(config, config_validation=True):
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.STATE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    req_state = config.get(CONF_STATE)
    for_period = config.get('for')

    def if_state(hass, variables=None):
        """Test if condition."""
        return state(hass, entity_id, req_state, for_period)

    return if_state


def sun(hass, before=None, after=None, before_offset=None, after_offset=None):
    """Test if current time matches sun requirements."""
    now = dt_util.now().time()
    before_offset = before_offset or timedelta(0)
    after_offset = after_offset or timedelta(0)

    if before == SUN_EVENT_SUNRISE and now > (sun_cmp.next_rising(hass) +
                                              before_offset).time():
        return False

    elif before == SUN_EVENT_SUNSET and now > (sun_cmp.next_setting(hass) +
                                               before_offset).time():
        return False

    if after == SUN_EVENT_SUNRISE and now < (sun_cmp.next_rising(hass) +
                                             after_offset).time():
        return False

    elif after == SUN_EVENT_SUNSET and now < (sun_cmp.next_setting(hass) +
                                              after_offset).time():
        return False

    return True


def sun_from_config(config, config_validation=True):
    """Wrap action method with sun based condition."""
    if config_validation:
        config = cv.SUN_CONDITION_SCHEMA(config)
    before = config.get('before')
    after = config.get('after')
    before_offset = config.get('before_offset')
    after_offset = config.get('after_offset')

    def time_if(hass, variables=None):
        """Validate time based if-condition."""
        return sun(hass, before, after, before_offset, after_offset)

    return time_if


def template(hass, value_template, variables=None):
    """Test if template condition matches."""
    try:
        value = render(hass, value_template, variables)
    except TemplateError as ex:
        _LOGGER.error('Error duriong template condition: %s', ex)
        return False

    return value.lower() == 'true'


def template_from_config(config, config_validation=True):
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.TEMPLATE_CONDITION_SCHEMA(config)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def template_if(hass, variables=None):
        """Validate template based if-condition."""
        return template(hass, value_template, variables)

    return template_if


def time(before=None, after=None, weekday=None):
    """Test if local time condition matches."""
    now = dt_util.now()
    now_time = now.time()

    if before is not None and now_time > before:
        return False

    if after is not None and now_time < after:
        return False

    if weekday is not None:
        now_weekday = WEEKDAYS[now.weekday()]

        if isinstance(weekday, str) and weekday != now_weekday or \
           now_weekday not in weekday:
            return False

    return True


def time_from_config(config, config_validation=True):
    """Wrap action method with time based condition."""
    if config_validation:
        config = cv.TIME_CONDITION_SCHEMA(config)
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    def time_if(hass, variables=None):
        """Validate time based if-condition."""
        return time(before, after, weekday)

    return time_if


def zone(hass, zone_ent, entity):
    """Test if zone-condition matches."""
    if isinstance(zone_ent, str):
        zone_ent = hass.states.get(zone_ent)

    if zone_ent is None:
        return False

    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None or longitude is None:
        return False

    return zone_cmp.in_zone(zone_ent, latitude, longitude,
                            entity.attributes.get(ATTR_GPS_ACCURACY, 0))


def zone_from_config(config, config_validation=True):
    """Wrap action method with zone based condition."""
    if config_validation:
        config = cv.ZONE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)

    def if_in_zone(hass, variables=None):
        """Test if condition."""
        return zone(hass, zone_entity_id, entity_id)

    return if_in_zone
