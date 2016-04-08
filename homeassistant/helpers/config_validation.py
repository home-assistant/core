"""Helpers for config validation using voluptuous."""
from datetime import timedelta

import jinja2
import voluptuous as vol

from homeassistant.loader import get_platform
from homeassistant.const import (
    CONF_PLATFORM, CONF_SCAN_INTERVAL, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import valid_entity_id
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify

# pylint: disable=invalid-name

# Home Assistant types
byte = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
small_float = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
latitude = vol.All(vol.Coerce(float), vol.Range(min=-90, max=90),
                   msg='invalid latitude')
longitude = vol.All(vol.Coerce(float), vol.Range(min=-180, max=180),
                    msg='invalid longitude')


def boolean(value):
    """Validate and coerce a boolean value."""
    if isinstance(value, str):
        value = value.lower()
        if value in ('1', 'true', 'yes', 'on', 'enable'):
            return True
        if value in ('0', 'false', 'no', 'off', 'disable'):
            return False
        raise vol.Invalid('invalid boolean value {}'.format(value))
    return bool(value)


def isfile(value):
    """Validate that the value is an existing file."""
    return vol.IsFile('not a file')(value)


def ensure_list(value):
    """Wrap value in list if it is not one."""
    return value if isinstance(value, list) else [value]


def entity_id(value):
    """Validate Entity ID."""
    if valid_entity_id(value):
        return value
    raise vol.Invalid('Entity ID {} does not match format <domain>.<object_id>'
                      .format(value))


def entity_ids(value):
    """Validate Entity IDs."""
    if isinstance(value, str):
        value = [ent_id.strip() for ent_id in value.split(',')]

    for ent_id in value:
        entity_id(ent_id)

    return value


def icon(value):
    """Validate icon."""
    value = str(value)

    if value.startswith('mdi:'):
        return value

    raise vol.Invalid('Icons should start with prefix "mdi:"')


def time_offset(value):
    """Validate and transform time offset."""
    if not isinstance(value, str):
        raise vol.Invalid('offset should be a string')

    negative_offset = False
    if value.startswith('-'):
        negative_offset = True
        value = value[1:]
    elif value.startswith('+'):
        value = value[1:]

    try:
        parsed = [int(x) for x in value.split(':')]
    except ValueError:
        raise vol.Invalid(
            'offset {} should be format HH:MM or HH:MM:SS'.format(value))

    if len(parsed) == 2:
        hour, minute = parsed
        second = 0
    elif len(parsed) == 3:
        hour, minute, second = parsed
    else:
        raise vol.Invalid(
            'offset {} should be format HH:MM or HH:MM:SS'.format(value))

    offset = timedelta(hours=hour, minutes=minute, seconds=second)

    if negative_offset:
        offset *= -1

    return offset


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


def string(value):
    """Coerce value to string, except for None."""
    if value is not None:
        return str(value)
    raise vol.Invalid('string value is None')


def temperature_unit(value):
    """Validate and transform temperature unit."""
    value = str(value).upper()
    if value == 'C':
        return TEMP_CELCIUS
    elif value == 'F':
        return TEMP_FAHRENHEIT
    raise vol.Invalid('invalid temperature unit (expected C or F)')


def template(value):
    """Validate a jinja2 template."""
    if value is None:
        raise vol.Invalid('template value is None')

    value = str(value)
    try:
        jinja2.Environment().parse(value)
        return value
    except jinja2.exceptions.TemplateSyntaxError as ex:
        raise vol.Invalid('invalid template ({})'.format(ex))


def time_zone(value):
    """Validate timezone."""
    if dt_util.get_time_zone(value) is not None:
        return value
    raise vol.Invalid(
        'Invalid time zone passed in. Valid options can be found here: '
        'http://en.wikipedia.org/wiki/List_of_tz_database_time_zones')


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


# Adapted from:
# https://github.com/alecthomas/voluptuous/issues/115#issuecomment-144464666
def has_at_least_one_key(*keys):
    """Validator that at least one key exists."""
    def validate(obj):
        """Test keys exist in dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid('expected dictionary')

        for k in obj.keys():
            if k in keys:
                return obj
        raise vol.Invalid('must contain one of {}.'.format(', '.join(keys)))

    return validate


# Schemas

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): string,
    CONF_SCAN_INTERVAL: vol.All(vol.Coerce(int), vol.Range(min=1)),
}, extra=vol.ALLOW_EXTRA)

EVENT_SCHEMA = vol.Schema({
    vol.Required('event'): string,
    'event_data': dict
})

SERVICE_SCHEMA = vol.All(vol.Schema({
    vol.Exclusive('service', 'service name'): service,
    vol.Exclusive('service_template', 'service name'): string,
    vol.Exclusive('data', 'service data'): dict,
    vol.Exclusive('data_template', 'service data'): {match_all: template},
    'entity_id': entity_ids,
}), has_at_least_one_key('service', 'service_template'))
