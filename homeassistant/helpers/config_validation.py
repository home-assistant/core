"""Helpers for config validation using voluptuous."""
import jinja2
import voluptuous as vol

from homeassistant.const import (
    CONF_PLATFORM, CONF_SCAN_INTERVAL, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import valid_entity_id
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify

# pylint: disable=invalid-name

# Home Assistant types

byte = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
small_float = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
latitude = vol.All(vol.Coerce(float), vol.Range(min=-90, max=90),
                   msg='invalid latitude')
longitude = vol.All(vol.Coerce(float), vol.Range(min=-180, max=180),
                    msg='invalid longitude')


def boolean(value):
    """Validate and coerce a boolean value."""
    if isinstance(value, str):
        if value in ('1', 'true', 'yes', 'on', 'enable'):
            return True
        if value in ('0', 'false', 'no', 'off', 'disable'):
            return False
        raise vol.Invalid('invalid boolean value {}'.format(value))
    return bool(value)


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

# pylint: disable=too-few-public-methods

class DictValidator(object):
    """Validate keys and values in a dictionary."""

    def __init__(self, value_validator=None, key_validator=None):
        """Initialize the dict validator."""
        if value_validator is not None:
            value_validator = vol.Schema(value_validator)

        self.value_validator = value_validator

        if key_validator is not None:
            key_validator = vol.Schema(key_validator)

        self.key_validator = key_validator

    def __call__(self, obj):
        """Validate the dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid('Expected dictionary.')

        errors = []

        # So we keep it an OrderedDict if it is one
        result = obj.__class__()

        for key, value in obj.items():
            if self.key_validator is not None:
                try:
                    key = self.key_validator(key)
                except vol.Invalid as ex:
                    errors.append('key {} is invalid ({})'.format(key, ex))

            if self.value_validator is not None:
                try:
                    value = self.value_validator(value)
                except vol.Invalid as ex:
                    errors.append(
                        'key {} contains invalid value ({})'.format(key, ex))

            if not errors:
                result[key] = value

        if errors:
            raise vol.Invalid(
                'invalid dictionary: {}'.format(', '.join(errors)))

        return result


# Adapted from:
# https://github.com/alecthomas/voluptuous/issues/115#issuecomment-144464666
def has_at_least_one_key(keys):
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
    vol.Exclusive('data_template', 'service data'): DictValidator(template),
}), has_at_least_one_key(['service', 'service_template']))
