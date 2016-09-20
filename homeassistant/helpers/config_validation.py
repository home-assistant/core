"""Helpers for config validation using voluptuous."""
from collections import OrderedDict
from datetime import timedelta
import os
from urllib.parse import urlparse

from typing import Any, Union, TypeVar, Callable, Sequence, Dict

import jinja2
import voluptuous as vol

from homeassistant.loader import get_platform
from homeassistant.const import (
    CONF_PLATFORM, CONF_SCAN_INTERVAL, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    CONF_ALIAS, CONF_ENTITY_ID, CONF_VALUE_TEMPLATE, WEEKDAYS,
    CONF_CONDITION, CONF_BELOW, CONF_ABOVE, SUN_EVENT_SUNSET,
    SUN_EVENT_SUNRISE, CONF_UNIT_SYSTEM_IMPERIAL, CONF_UNIT_SYSTEM_METRIC)
from homeassistant.core import valid_entity_id
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify

# pylint: disable=invalid-name

TIME_PERIOD_ERROR = "offset {} should be format 'HH:MM' or 'HH:MM:SS'"

# Home Assistant types
byte = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
small_float = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
latitude = vol.All(vol.Coerce(float), vol.Range(min=-90, max=90),
                   msg='invalid latitude')
longitude = vol.All(vol.Coerce(float), vol.Range(min=-180, max=180),
                    msg='invalid longitude')
sun_event = vol.All(vol.Lower, vol.Any(SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE))
port = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))

# typing typevar
T = TypeVar('T')


# Adapted from:
# https://github.com/alecthomas/voluptuous/issues/115#issuecomment-144464666
def has_at_least_one_key(*keys: str) -> Callable:
    """Validator that at least one key exists."""
    def validate(obj: Dict) -> Dict:
        """Test keys exist in dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid('expected dictionary')

        for k in obj.keys():
            if k in keys:
                return obj
        raise vol.Invalid('must contain one of {}.'.format(', '.join(keys)))

    return validate


def boolean(value: Any) -> bool:
    """Validate and coerce a boolean value."""
    if isinstance(value, str):
        value = value.lower()
        if value in ('1', 'true', 'yes', 'on', 'enable'):
            return True
        if value in ('0', 'false', 'no', 'off', 'disable'):
            return False
        raise vol.Invalid('invalid boolean value {}'.format(value))
    return bool(value)


def isfile(value: Any) -> str:
    """Validate that the value is an existing file."""
    if value is None:
        raise vol.Invalid('None is not file')
    file_in = os.path.expanduser(str(value))

    if not os.path.isfile(file_in):
        raise vol.Invalid('not a file')
    if not os.access(file_in, os.R_OK):
        raise vol.Invalid('file not readable')
    return file_in


def ensure_list(value: Union[T, Sequence[T]]) -> Sequence[T]:
    """Wrap value in list if it is not one."""
    return value if isinstance(value, list) else [value]


def entity_id(value: Any) -> str:
    """Validate Entity ID."""
    value = string(value).lower()
    if valid_entity_id(value):
        return value
    raise vol.Invalid('Entity ID {} is an invalid entity id'.format(value))


def entity_ids(value: Union[str, Sequence]) -> Sequence[str]:
    """Validate Entity IDs."""
    if value is None:
        raise vol.Invalid('Entity IDs can not be None')
    if isinstance(value, str):
        value = [ent_id.strip() for ent_id in value.split(',')]

    return [entity_id(ent_id) for ent_id in value]


def icon(value):
    """Validate icon."""
    value = str(value)

    if value.startswith('mdi:'):
        return value

    raise vol.Invalid('Icons should start with prefix "mdi:"')


time_period_dict = vol.All(
    dict, vol.Schema({
        'days': vol.Coerce(int),
        'hours': vol.Coerce(int),
        'minutes': vol.Coerce(int),
        'seconds': vol.Coerce(int),
        'milliseconds': vol.Coerce(int),
    }),
    has_at_least_one_key('days', 'hours', 'minutes',
                         'seconds', 'milliseconds'),
    lambda value: timedelta(**value))


def time_period_str(value: str) -> timedelta:
    """Validate and transform time offset."""
    if isinstance(value, int):
        raise vol.Invalid('Make sure you wrap time values in quotes')
    elif not isinstance(value, str):
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    negative_offset = False
    if value.startswith('-'):
        negative_offset = True
        value = value[1:]
    elif value.startswith('+'):
        value = value[1:]

    try:
        parsed = [int(x) for x in value.split(':')]
    except ValueError:
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    if len(parsed) == 2:
        hour, minute = parsed
        second = 0
    elif len(parsed) == 3:
        hour, minute, second = parsed
    else:
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    offset = timedelta(hours=hour, minutes=minute, seconds=second)

    if negative_offset:
        offset *= -1

    return offset


time_period = vol.Any(time_period_str, timedelta, time_period_dict)


def match_all(value):
    """Validator that matches all values."""
    return value


def platform_validator(domain):
    """Validate if platform exists for given domain."""
    def validator(value):
        """Test if platform exists."""
        if value is None:
            raise vol.Invalid('platform cannot be None')
        if get_platform(domain, str(value)):
            return value
        raise vol.Invalid(
            'platform {} does not exist for {}'.format(value, domain))
    return validator


def positive_timedelta(value: timedelta) -> timedelta:
    """Validate timedelta is positive."""
    if value < timedelta(0):
        raise vol.Invalid('Time period should be positive')
    return value


def service(value):
    """Validate service."""
    # Services use same format as entities so we can use same helper.
    if valid_entity_id(value):
        return value
    raise vol.Invalid('Service {} does not match format <domain>.<name>'
                      .format(value))


def slug(value):
    """Validate value is a valid slug."""
    if value is None:
        raise vol.Invalid('Slug should not be None')
    value = str(value)
    slg = slugify(value)
    if value == slg:
        return value
    raise vol.Invalid('invalid slug {} (try {})'.format(value, slg))


def string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is not None:
        return str(value)
    raise vol.Invalid('string value is None')


def temperature_unit(value) -> str:
    """Validate and transform temperature unit."""
    value = str(value).upper()
    if value == 'C':
        return TEMP_CELSIUS
    elif value == 'F':
        return TEMP_FAHRENHEIT
    raise vol.Invalid('invalid temperature unit (expected C or F)')


unit_system = vol.All(vol.Lower, vol.Any(CONF_UNIT_SYSTEM_METRIC,
                                         CONF_UNIT_SYSTEM_IMPERIAL))


def template(value):
    """Validate a jinja2 template."""
    if value is None:
        raise vol.Invalid('template value is None')
    if isinstance(value, (list, dict)):
        raise vol.Invalid('template value should be a string')

    value = str(value)
    try:
        jinja2.Environment().parse(value)
        return value
    except jinja2.exceptions.TemplateSyntaxError as ex:
        raise vol.Invalid('invalid template ({})'.format(ex))


def template_complex(value):
    """Validate a complex jinja2 template."""
    if isinstance(value, list):
        for idx, element in enumerate(value):
            value[idx] = template_complex(element)
        return value
    if isinstance(value, dict):
        for key, element in value.items():
            value[key] = template_complex(element)
        return value

    return template(value)


def time(value):
    """Validate time."""
    time_val = dt_util.parse_time(value)

    if time_val is None:
        raise vol.Invalid('Invalid time specified: {}'.format(value))

    return time_val


def time_zone(value):
    """Validate timezone."""
    if dt_util.get_time_zone(value) is not None:
        return value
    raise vol.Invalid(
        'Invalid time zone passed in. Valid options can be found here: '
        'http://en.wikipedia.org/wiki/List_of_tz_database_time_zones')

weekdays = vol.All(ensure_list, [vol.In(WEEKDAYS)])


# pylint: disable=no-value-for-parameter
def url(value: Any) -> str:
    """Validate an URL."""
    url_in = str(value)

    if urlparse(url_in).scheme in ['http', 'https']:
        return vol.Schema(vol.Url())(url_in)

    raise vol.Invalid('invalid url')


def ordered_dict(value_validator, key_validator=match_all):
    """Validate an ordered dict validator that maintains ordering.

    value_validator will be applied to each value of the dictionary.
    key_validator (optional) will be applied to each key of the dictionary.
    """
    item_validator = vol.Schema({key_validator: value_validator})

    def validator(value):
        """Validate ordered dict."""
        config = OrderedDict()

        for key, val in value.items():
            v_res = item_validator({key: val})
            config.update(v_res)

        return config

    return validator


# Validator helpers

def key_dependency(key, dependency):
    """Validate that all dependencies exist for key."""
    def validator(value):
        """Test dependencies."""
        if not isinstance(value, dict):
            raise vol.Invalid('key dependencies require a dict')
        if key in value and dependency not in value:
            raise vol.Invalid('dependency violation - key "{}" requires '
                              'key "{}" to exist'.format(key, dependency))

        return value
    return validator


# Schemas

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): string,
    CONF_SCAN_INTERVAL: vol.All(vol.Coerce(int), vol.Range(min=1)),
}, extra=vol.ALLOW_EXTRA)

EVENT_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): string,
    vol.Required('event'): string,
    vol.Optional('event_data'): dict,
})

SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Optional(CONF_ALIAS): string,
    vol.Exclusive('service', 'service name'): service,
    vol.Exclusive('service_template', 'service name'): template,
    vol.Optional('data'): dict,
    vol.Optional('data_template'): {match_all: template_complex},
    vol.Optional(CONF_ENTITY_ID): entity_ids,
}), has_at_least_one_key('service', 'service_template'))

NUMERIC_STATE_CONDITION_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_CONDITION): 'numeric_state',
    vol.Required(CONF_ENTITY_ID): entity_id,
    CONF_BELOW: vol.Coerce(float),
    CONF_ABOVE: vol.Coerce(float),
    vol.Optional(CONF_VALUE_TEMPLATE): template,
}), has_at_least_one_key(CONF_BELOW, CONF_ABOVE))

STATE_CONDITION_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_CONDITION): 'state',
    vol.Required(CONF_ENTITY_ID): entity_id,
    vol.Required('state'): str,
    vol.Optional('for'): vol.All(time_period, positive_timedelta),
    # To support use_trigger_value in automation
    # Deprecated 2016/04/25
    vol.Optional('from'): str,
}), key_dependency('for', 'state'))

SUN_CONDITION_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_CONDITION): 'sun',
    vol.Optional('before'): sun_event,
    vol.Optional('before_offset'): time_period,
    vol.Optional('after'): vol.All(vol.Lower, vol.Any('sunset', 'sunrise')),
    vol.Optional('after_offset'): time_period,
}), has_at_least_one_key('before', 'after'))

TEMPLATE_CONDITION_SCHEMA = vol.Schema({
    vol.Required(CONF_CONDITION): 'template',
    vol.Required(CONF_VALUE_TEMPLATE): template,
})

TIME_CONDITION_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_CONDITION): 'time',
    'before': time,
    'after': time,
    'weekday': weekdays,
}), has_at_least_one_key('before', 'after', 'weekday'))

ZONE_CONDITION_SCHEMA = vol.Schema({
    vol.Required(CONF_CONDITION): 'zone',
    vol.Required(CONF_ENTITY_ID): entity_id,
    'zone': entity_id,
    # To support use_trigger_value in automation
    # Deprecated 2016/04/25
    vol.Optional('event'): vol.Any('enter', 'leave'),
})

AND_CONDITION_SCHEMA = vol.Schema({
    vol.Required(CONF_CONDITION): 'and',
    vol.Required('conditions'): vol.All(
        ensure_list,
        # pylint: disable=unnecessary-lambda
        [lambda value: CONDITION_SCHEMA(value)],
    )
})

OR_CONDITION_SCHEMA = vol.Schema({
    vol.Required(CONF_CONDITION): 'or',
    vol.Required('conditions'): vol.All(
        ensure_list,
        # pylint: disable=unnecessary-lambda
        [lambda value: CONDITION_SCHEMA(value)],
    )
})

CONDITION_SCHEMA = vol.Any(
    NUMERIC_STATE_CONDITION_SCHEMA,
    STATE_CONDITION_SCHEMA,
    SUN_CONDITION_SCHEMA,
    TEMPLATE_CONDITION_SCHEMA,
    TIME_CONDITION_SCHEMA,
    ZONE_CONDITION_SCHEMA,
    AND_CONDITION_SCHEMA,
    OR_CONDITION_SCHEMA,
)

_SCRIPT_DELAY_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): string,
    vol.Required("delay"): vol.Any(
        vol.All(time_period, positive_timedelta),
        template)
})

SCRIPT_SCHEMA = vol.All(
    ensure_list,
    [vol.Any(SERVICE_SCHEMA, _SCRIPT_DELAY_SCHEMA, EVENT_SCHEMA,
             CONDITION_SCHEMA)],
)
