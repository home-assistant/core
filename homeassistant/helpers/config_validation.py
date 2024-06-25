"""Helpers for config validation using voluptuous."""

# PEP 563 seems to break typing.get_type_hints when used
# with PEP 695 syntax. Fixed in Python 3.13.
# from __future__ import annotations

from collections.abc import Callable, Hashable
import contextlib
from datetime import (
    date as date_sys,
    datetime as datetime_sys,
    time as time_sys,
    timedelta,
)
from enum import Enum, StrEnum
import logging
from numbers import Number
import os
import re
from socket import (  # type: ignore[attr-defined]  # private, not in typeshed
    _GLOBAL_DEFAULT_TIMEOUT,
)
from typing import Any, cast, overload
from urllib.parse import urlparse
from uuid import UUID

import voluptuous as vol
import voluptuous_serialize

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ABOVE,
    CONF_ALIAS,
    CONF_ATTRIBUTE,
    CONF_BELOW,
    CONF_CHOOSE,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_CONTINUE_ON_ERROR,
    CONF_CONTINUE_ON_TIMEOUT,
    CONF_COUNT,
    CONF_DEFAULT,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_ENTITY_NAMESPACE,
    CONF_ERROR,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_EVENT_DATA_TEMPLATE,
    CONF_FOR,
    CONF_FOR_EACH,
    CONF_ID,
    CONF_IF,
    CONF_MATCH,
    CONF_PARALLEL,
    CONF_PLATFORM,
    CONF_REPEAT,
    CONF_RESPONSE_VARIABLE,
    CONF_SCAN_INTERVAL,
    CONF_SCENE,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_SERVICE_DATA_TEMPLATE,
    CONF_SERVICE_TEMPLATE,
    CONF_SET_CONVERSATION_RESPONSE,
    CONF_STATE,
    CONF_STOP,
    CONF_TARGET,
    CONF_THEN,
    CONF_TIMEOUT,
    CONF_UNTIL,
    CONF_VALUE_TEMPLATE,
    CONF_VARIABLES,
    CONF_WAIT_FOR_TRIGGER,
    CONF_WAIT_TEMPLATE,
    CONF_WHILE,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_ANY,
    ENTITY_MATCH_NONE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
    WEEKDAYS,
    UnitOfTemperature,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    async_get_hass,
    async_get_hass_or_none,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.generated import currencies
from homeassistant.generated.countries import COUNTRIES
from homeassistant.generated.languages import LANGUAGES
from homeassistant.util import raise_if_invalid_path, slugify as util_slugify
import homeassistant.util.dt as dt_util
from homeassistant.util.yaml.objects import NodeStrClass

from . import script_variables as script_variables_helper, template as template_helper
from .frame import get_integration_logger

TIME_PERIOD_ERROR = "offset {} should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F'"


class UrlProtocolSchema(StrEnum):
    """Valid URL protocol schema values."""

    HTTP = "http"
    HTTPS = "https"
    HOMEASSISTANT = "homeassistant"


EXTERNAL_URL_PROTOCOL_SCHEMA_LIST = frozenset(
    {UrlProtocolSchema.HTTP, UrlProtocolSchema.HTTPS}
)
CONFIGURATION_URL_PROTOCOL_SCHEMA_LIST = frozenset(
    {UrlProtocolSchema.HOMEASSISTANT, UrlProtocolSchema.HTTP, UrlProtocolSchema.HTTPS}
)

# Home Assistant types
byte = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
small_float = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
positive_float = vol.All(vol.Coerce(float), vol.Range(min=0))
latitude = vol.All(
    vol.Coerce(float), vol.Range(min=-90, max=90), msg="invalid latitude"
)
longitude = vol.All(
    vol.Coerce(float), vol.Range(min=-180, max=180), msg="invalid longitude"
)
gps = vol.ExactSequence([latitude, longitude])
sun_event = vol.All(vol.Lower, vol.Any(SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE))
port = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))


def path(value: Any) -> str:
    """Validate it's a safe path."""
    if not isinstance(value, str):
        raise vol.Invalid("Expected a string")

    try:
        raise_if_invalid_path(value)
    except ValueError as err:
        raise vol.Invalid("Invalid path") from err

    return value


# Adapted from:
# https://github.com/alecthomas/voluptuous/issues/115#issuecomment-144464666
def has_at_least_one_key(*keys: Any) -> Callable[[dict], dict]:
    """Validate that at least one key exists."""
    key_set = set(keys)

    def validate(obj: dict) -> dict:
        """Test keys exist in dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid("expected dictionary")

        if not key_set.isdisjoint(obj):
            return obj
        expected = ", ".join(str(k) for k in keys)
        raise vol.Invalid(f"must contain at least one of {expected}.")

    return validate


def has_at_most_one_key(*keys: Any) -> Callable[[dict], dict]:
    """Validate that zero keys exist or one key exists."""

    def validate(obj: dict) -> dict:
        """Test zero keys exist or one key exists in dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid("expected dictionary")

        if len(set(keys) & set(obj)) > 1:
            expected = ", ".join(str(k) for k in keys)
            raise vol.Invalid(f"must contain at most one of {expected}.")
        return obj

    return validate


def boolean(value: Any) -> bool:
    """Validate and coerce a boolean value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("1", "true", "yes", "on", "enable"):
            return True
        if value in ("0", "false", "no", "off", "disable"):
            return False
    elif isinstance(value, Number):
        # type ignore: https://github.com/python/mypy/issues/3186
        return value != 0  # type: ignore[comparison-overlap]
    raise vol.Invalid(f"invalid boolean value {value}")


def whitespace(value: Any) -> str:
    """Validate result contains only whitespace."""
    if isinstance(value, str) and (value == "" or value.isspace()):
        return value

    raise vol.Invalid(f"contains non-whitespace: {value}")


def isdevice(value: Any) -> str:
    """Validate that value is a real device."""
    try:
        os.stat(value)
        return str(value)
    except OSError as err:
        raise vol.Invalid(f"No device at {value} found") from err


def matches_regex(regex: str) -> Callable[[Any], str]:
    """Validate that the value is a string that matches a regex."""
    compiled = re.compile(regex)

    def validator(value: Any) -> str:
        """Validate that value matches the given regex."""
        if not isinstance(value, str):
            raise vol.Invalid(f"not a string value: {value}")

        if not compiled.match(value):
            raise vol.Invalid(
                f"value {value} does not match regular expression {compiled.pattern}"
            )

        return value

    return validator


def is_regex(value: Any) -> re.Pattern[Any]:
    """Validate that a string is a valid regular expression."""
    try:
        r = re.compile(value)
    except TypeError as err:
        raise vol.Invalid(
            f"value {value} is of the wrong type for a regular expression"
        ) from err
    except re.error as err:
        raise vol.Invalid(f"value {value} is not a valid regular expression") from err
    return r


def isfile(value: Any) -> str:
    """Validate that the value is an existing file."""
    if value is None:
        raise vol.Invalid("None is not file")
    file_in = os.path.expanduser(str(value))

    if not os.path.isfile(file_in):
        raise vol.Invalid("not a file")
    if not os.access(file_in, os.R_OK):
        raise vol.Invalid("file not readable")
    return file_in


def isdir(value: Any) -> str:
    """Validate that the value is an existing dir."""
    if value is None:
        raise vol.Invalid("not a directory")
    dir_in = os.path.expanduser(str(value))

    if not os.path.isdir(dir_in):
        raise vol.Invalid("not a directory")
    if not os.access(dir_in, os.R_OK):
        raise vol.Invalid("directory not readable")
    return dir_in


@overload
def ensure_list(value: None) -> list[Any]: ...


@overload
def ensure_list[_T](value: list[_T]) -> list[_T]: ...


@overload
def ensure_list[_T](value: list[_T] | _T) -> list[_T]: ...


def ensure_list[_T](value: _T | None) -> list[_T] | list[Any]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return cast("list[_T]", value) if isinstance(value, list) else [value]


def entity_id(value: Any) -> str:
    """Validate Entity ID."""
    str_value = string(value).lower()
    if valid_entity_id(str_value):
        return str_value

    raise vol.Invalid(f"Entity ID {value} is an invalid entity ID")


def entity_id_or_uuid(value: Any) -> str:
    """Validate Entity specified by entity_id or uuid."""
    with contextlib.suppress(vol.Invalid):
        return entity_id(value)
    with contextlib.suppress(vol.Invalid):
        return fake_uuid4_hex(value)
    raise vol.Invalid(f"Entity {value} is neither a valid entity ID nor a valid UUID")


def _entity_ids(value: str | list, allow_uuid: bool) -> list[str]:
    """Help validate entity IDs or UUIDs."""
    if value is None:
        raise vol.Invalid("Entity IDs cannot be None")
    if isinstance(value, str):
        value = [ent_id.strip() for ent_id in value.split(",")]

    validator = entity_id_or_uuid if allow_uuid else entity_id
    return [validator(ent_id) for ent_id in value]


def entity_ids(value: str | list) -> list[str]:
    """Validate Entity IDs."""
    return _entity_ids(value, False)


def entity_ids_or_uuids(value: str | list) -> list[str]:
    """Validate entities specified by entity IDs or UUIDs."""
    return _entity_ids(value, True)


comp_entity_ids = vol.Any(
    vol.All(vol.Lower, vol.Any(ENTITY_MATCH_ALL, ENTITY_MATCH_NONE)), entity_ids
)


comp_entity_ids_or_uuids = vol.Any(
    vol.All(vol.Lower, vol.Any(ENTITY_MATCH_ALL, ENTITY_MATCH_NONE)),
    entity_ids_or_uuids,
)


def domain_key(config_key: Any) -> str:
    """Validate a top level config key with an optional label and return the domain.

    A domain is separated from a label by one or more spaces, empty labels are not
    allowed.

    Examples:
    'hue' returns 'hue'
    'hue 1' returns 'hue'
    'hue  1' returns 'hue'
    'hue ' raises
    'hue  ' raises

    """
    if not isinstance(config_key, str):
        raise vol.Invalid("invalid domain", path=[config_key])

    parts = config_key.partition(" ")
    _domain = parts[0] if parts[2].strip(" ") else config_key
    if not _domain or _domain.strip(" ") != _domain:
        raise vol.Invalid("invalid domain", path=[config_key])

    return _domain


def entity_domain(domain: str | list[str]) -> Callable[[Any], str]:
    """Validate that entity belong to domain."""
    ent_domain = entities_domain(domain)

    def validate(value: str) -> str:
        """Test if entity domain is domain."""
        validated = ent_domain(value)
        if len(validated) != 1:
            raise vol.Invalid(f"Expected exactly 1 entity, got {len(validated)}")
        return validated[0]

    return validate


def entities_domain(domain: str | list[str]) -> Callable[[str | list], list[str]]:
    """Validate that entities belong to domain."""
    if isinstance(domain, str):

        def check_invalid(val: str) -> bool:
            return val != domain

    else:

        def check_invalid(val: str) -> bool:
            return val not in domain

    def validate(values: str | list) -> list[str]:
        """Test if entity domain is domain."""
        values = entity_ids(values)
        for ent_id in values:
            if check_invalid(split_entity_id(ent_id)[0]):
                raise vol.Invalid(
                    f"Entity ID '{ent_id}' does not belong to domain '{domain}'"
                )
        return values

    return validate


def enum(enumClass: type[Enum]) -> vol.All:
    """Create validator for specified enum."""
    return vol.All(vol.In(enumClass.__members__), enumClass.__getitem__)


def icon(value: Any) -> str:
    """Validate icon."""
    str_value = str(value)

    if ":" in str_value:
        return str_value

    raise vol.Invalid('Icons should be specified in the form "prefix:name"')


_COLOR_HEX = re.compile(r"^#[0-9A-F]{6}$", re.IGNORECASE)


def color_hex(value: Any) -> str:
    """Validate a hex color code."""
    str_value = str(value)

    if not _COLOR_HEX.match(str_value):
        raise vol.Invalid("Color should be in the format #RRGGBB")

    return str_value


_TIME_PERIOD_DICT_KEYS = ("days", "hours", "minutes", "seconds", "milliseconds")

time_period_dict = vol.All(
    dict,
    vol.Schema(
        {
            "days": vol.Coerce(float),
            "hours": vol.Coerce(float),
            "minutes": vol.Coerce(float),
            "seconds": vol.Coerce(float),
            "milliseconds": vol.Coerce(float),
        }
    ),
    has_at_least_one_key(*_TIME_PERIOD_DICT_KEYS),
    lambda value: timedelta(**value),
)


def time(value: Any) -> time_sys:
    """Validate and transform a time."""
    if isinstance(value, time_sys):
        return value

    try:
        time_val = dt_util.parse_time(value)
    except TypeError as err:
        raise vol.Invalid("Not a parseable type") from err

    if time_val is None:
        raise vol.Invalid(f"Invalid time specified: {value}")

    return time_val


def date(value: Any) -> date_sys:
    """Validate and transform a date."""
    if isinstance(value, date_sys):
        return value

    try:
        date_val = dt_util.parse_date(value)
    except TypeError as err:
        raise vol.Invalid("Not a parseable type") from err

    if date_val is None:
        raise vol.Invalid("Could not parse date")

    return date_val


def time_period_str(value: str) -> timedelta:
    """Validate and transform time offset."""
    if isinstance(value, int):  # type: ignore[unreachable]
        raise vol.Invalid("Make sure you wrap time values in quotes")
    if not isinstance(value, str):
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    negative_offset = False
    if value.startswith("-"):
        negative_offset = True
        value = value[1:]
    elif value.startswith("+"):
        value = value[1:]

    parsed = value.split(":")
    if len(parsed) not in (2, 3):
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))
    try:
        hour = int(parsed[0])
        minute = int(parsed[1])
        try:
            second = float(parsed[2])
        except IndexError:
            second = 0
    except ValueError as err:
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value)) from err

    offset = timedelta(hours=hour, minutes=minute, seconds=second)

    if negative_offset:
        offset *= -1

    return offset


def time_period_seconds(value: float | str) -> timedelta:
    """Validate and transform seconds to a time offset."""
    try:
        return timedelta(seconds=float(value))
    except (ValueError, TypeError) as err:
        raise vol.Invalid(f"Expected seconds, got {value}") from err


time_period = vol.Any(time_period_str, time_period_seconds, timedelta, time_period_dict)


def match_all[_T](value: _T) -> _T:
    """Validate that matches all values."""
    return value


def positive_timedelta(value: timedelta) -> timedelta:
    """Validate timedelta is positive."""
    if value < timedelta(0):
        raise vol.Invalid("Time period should be positive")
    return value


positive_time_period_dict = vol.All(time_period_dict, positive_timedelta)
positive_time_period = vol.All(time_period, positive_timedelta)


def remove_falsy[_T](value: list[_T]) -> list[_T]:
    """Remove falsy values from a list."""
    return [v for v in value if v]


def service(value: Any) -> str:
    """Validate service."""
    # Services use same format as entities so we can use same helper.
    str_value = string(value).lower()
    if valid_entity_id(str_value):
        return str_value

    raise vol.Invalid(f"Service {value} does not match format <domain>.<name>")


def slug(value: Any) -> str:
    """Validate value is a valid slug."""
    if value is None:
        raise vol.Invalid("Slug should not be None")
    str_value = str(value)
    slg = util_slugify(str_value)
    if str_value == slg:
        return str_value
    raise vol.Invalid(f"invalid slug {value} (try {slg})")


def schema_with_slug_keys(
    value_schema: dict | Callable, *, slug_validator: Callable[[Any], str] = slug
) -> Callable:
    """Ensure dicts have slugs as keys.

    Replacement of vol.Schema({cv.slug: value_schema}) to prevent misleading
    "Extra keys" errors from voluptuous.
    """
    schema = vol.Schema({str: value_schema})

    def verify(value: dict) -> dict:
        """Validate all keys are slugs and then the value_schema."""
        if not isinstance(value, dict):
            raise vol.Invalid("expected dictionary")

        for key in value:
            slug_validator(key)

        return cast(dict, schema(value))

    return verify


def slugify(value: Any) -> str:
    """Coerce a value to a slug."""
    if value is None:
        raise vol.Invalid("Slug should not be None")
    slg = util_slugify(str(value))
    if slg:
        return slg
    raise vol.Invalid(f"Unable to slugify {value}")


def string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is None:
        raise vol.Invalid("string value is None")

    # This is expected to be the most common case, so check it first.
    if (
        type(value) is str  # noqa: E721
        or type(value) is NodeStrClass
        or isinstance(value, str)
    ):
        return value

    if isinstance(value, template_helper.ResultWrapper):
        value = value.render_result

    elif isinstance(value, (list, dict)):
        raise vol.Invalid("value should be a string")

    return str(value)


def string_with_no_html(value: Any) -> str:
    """Validate that the value is a string without HTML."""
    value = string(value)
    regex = re.compile(r"<[a-z].*?>", re.IGNORECASE)
    if regex.search(value):
        raise vol.Invalid("the string should not contain HTML")
    return str(value)


def temperature_unit(value: Any) -> UnitOfTemperature:
    """Validate and transform temperature unit."""
    value = str(value).upper()
    if value == "C":
        return UnitOfTemperature.CELSIUS
    if value == "F":
        return UnitOfTemperature.FAHRENHEIT
    raise vol.Invalid("invalid temperature unit (expected C or F)")


def template(value: Any | None) -> template_helper.Template:
    """Validate a jinja2 template."""
    if value is None:
        raise vol.Invalid("template value is None")
    if isinstance(value, (list, dict, template_helper.Template)):
        raise vol.Invalid("template value should be a string")

    template_value = template_helper.Template(str(value), async_get_hass_or_none())

    try:
        template_value.ensure_valid()
    except TemplateError as ex:
        raise vol.Invalid(f"invalid template ({ex})") from ex
    return template_value


def dynamic_template(value: Any | None) -> template_helper.Template:
    """Validate a dynamic (non static) jinja2 template."""
    if value is None:
        raise vol.Invalid("template value is None")
    if isinstance(value, (list, dict, template_helper.Template)):
        raise vol.Invalid("template value should be a string")
    if not template_helper.is_template_string(str(value)):
        raise vol.Invalid("template value does not contain a dynamic template")

    template_value = template_helper.Template(str(value), async_get_hass_or_none())

    try:
        template_value.ensure_valid()
    except TemplateError as ex:
        raise vol.Invalid(f"invalid template ({ex})") from ex
    return template_value


def template_complex(value: Any) -> Any:
    """Validate a complex jinja2 template."""
    if isinstance(value, list):
        return_list = value.copy()
        for idx, element in enumerate(return_list):
            return_list[idx] = template_complex(element)
        return return_list
    if isinstance(value, dict):
        return {
            template_complex(key): template_complex(element)
            for key, element in value.items()
        }
    if isinstance(value, str) and template_helper.is_template_string(value):
        return template(value)

    return value


def _positive_time_period_template_complex(value: Any) -> Any:
    """Do basic validation of a positive time period expressed as a templated dict."""
    if not isinstance(value, dict) or not value:
        raise vol.Invalid("template should be a dict")
    for key, element in value.items():
        if not isinstance(key, str):
            raise vol.Invalid("key should be a string")
        if not template_helper.is_template_string(key):
            vol.In(_TIME_PERIOD_DICT_KEYS)(key)
        if not isinstance(element, str) or (
            isinstance(element, str) and not template_helper.is_template_string(element)
        ):
            vol.All(vol.Coerce(float), vol.Range(min=0))(element)
    return template_complex(value)


positive_time_period_template = vol.Any(
    positive_time_period, dynamic_template, _positive_time_period_template_complex
)


def datetime(value: Any) -> datetime_sys:
    """Validate datetime."""
    if isinstance(value, datetime_sys):
        return value

    try:
        date_val = dt_util.parse_datetime(value)
    except TypeError:
        date_val = None

    if date_val is None:
        raise vol.Invalid(f"Invalid datetime specified: {value}")

    return date_val


def time_zone(value: str) -> str:
    """Validate timezone."""
    if dt_util.get_time_zone(value) is not None:
        return value
    raise vol.Invalid(
        "Invalid time zone passed in. Valid options can be found here: "
        "http://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
    )


weekdays = vol.All(ensure_list, [vol.In(WEEKDAYS)])


def socket_timeout(value: Any | None) -> object:
    """Validate timeout float > 0.0.

    None coerced to socket._GLOBAL_DEFAULT_TIMEOUT bare object.
    """
    if value is None:
        return _GLOBAL_DEFAULT_TIMEOUT
    try:
        float_value = float(value)
        if float_value > 0.0:
            return float_value
        raise vol.Invalid("Invalid socket timeout value. float > 0.0 required.")
    except Exception as err:
        raise vol.Invalid(f"Invalid socket timeout: {err}") from err


def url(
    value: Any,
    _schema_list: frozenset[UrlProtocolSchema] = EXTERNAL_URL_PROTOCOL_SCHEMA_LIST,
) -> str:
    """Validate an URL."""
    url_in = str(value)

    if urlparse(url_in).scheme in _schema_list:
        return cast(str, vol.Schema(vol.Url())(url_in))

    raise vol.Invalid("invalid url")


def configuration_url(value: Any) -> str:
    """Validate an URL that allows the homeassistant schema."""
    return url(value, CONFIGURATION_URL_PROTOCOL_SCHEMA_LIST)


def url_no_path(value: Any) -> str:
    """Validate a url without a path."""
    url_in = url(value)

    if urlparse(url_in).path not in ("", "/"):
        raise vol.Invalid("url it not allowed to have a path component")

    return url_in


def x10_address(value: str) -> str:
    """Validate an x10 address."""
    regex = re.compile(r"([A-Pa-p]{1})(?:[2-9]|1[0-6]?)$")
    if not regex.match(value):
        raise vol.Invalid("Invalid X10 Address")
    return str(value).lower()


def uuid4_hex(value: Any) -> str:
    """Validate a v4 UUID in hex format."""
    try:
        result = UUID(value, version=4)
    except (ValueError, AttributeError, TypeError) as error:
        raise vol.Invalid("Invalid Version4 UUID", error_message=str(error)) from error

    if result.hex != value.lower():
        # UUID() will create a uuid4 if input is invalid
        raise vol.Invalid("Invalid Version4 UUID")

    return result.hex


_FAKE_UUID_4_HEX = re.compile(r"^[0-9a-f]{32}$")


def fake_uuid4_hex(value: Any) -> str:
    """Validate a fake v4 UUID generated by random_uuid_hex."""
    try:
        if not _FAKE_UUID_4_HEX.match(value):
            raise vol.Invalid("Invalid UUID")
    except TypeError as exc:
        raise vol.Invalid("Invalid UUID") from exc
    return cast(str, value)  # Pattern.match throws if input is not a string


def ensure_list_csv(value: Any) -> list:
    """Ensure that input is a list or make one from comma-separated string."""
    if isinstance(value, str):
        return [member.strip() for member in value.split(",")]
    return ensure_list(value)


class multi_select:
    """Multi select validator returning list of selected values."""

    def __init__(self, options: dict | list) -> None:
        """Initialize multi select."""
        self.options = options

    def __call__(self, selected: list) -> list:
        """Validate input."""
        if not isinstance(selected, list):
            raise vol.Invalid("Not a list")

        for value in selected:
            if value not in self.options:
                raise vol.Invalid(f"{value} is not a valid option")

        return selected


def _deprecated_or_removed(
    key: str,
    replacement_key: str | None,
    default: Any | None,
    raise_if_present: bool,
    option_removed: bool,
) -> Callable[[dict], dict]:
    """Log key as deprecated and provide a replacement (if exists) or fail.

    Expected behavior:
        - Outputs or throws the appropriate deprecation warning if key is detected
        - Outputs or throws the appropriate error if key is detected
          and removed from support
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
    """

    def validator(config: dict) -> dict:
        """Check if key is in config and log warning or error."""
        if key in config:
            if option_removed:
                level = logging.ERROR
                option_status = "has been removed"
            else:
                level = logging.WARNING
                option_status = "is deprecated"

            try:
                near = (
                    f"near {config.__config_file__}"  # type: ignore[attr-defined]
                    f":{config.__line__} "  # type: ignore[attr-defined]
                )
            except AttributeError:
                near = ""
            arguments: tuple[str, ...]
            if replacement_key:
                warning = "The '%s' option %s%s, please replace it with '%s'"
                arguments = (key, near, option_status, replacement_key)
            else:
                warning = (
                    "The '%s' option %s%s, please remove it from your configuration"
                )
                arguments = (key, near, option_status)

            if raise_if_present:
                raise vol.Invalid(warning % arguments)

            get_integration_logger(__name__).log(level, warning, *arguments)
            value = config[key]
            if replacement_key or option_removed:
                config.pop(key)
        else:
            value = default

        keys = [key]
        if replacement_key:
            keys.append(replacement_key)
            if value is not None and (
                replacement_key not in config or default == config.get(replacement_key)
            ):
                config[replacement_key] = value

        return has_at_most_one_key(*keys)(config)

    return validator


def deprecated(
    key: str,
    replacement_key: str | None = None,
    default: Any | None = None,
    raise_if_present: bool | None = False,
) -> Callable[[dict], dict]:
    """Log key as deprecated and provide a replacement (if exists).

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
          or raises an exception
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
    """
    return _deprecated_or_removed(
        key,
        replacement_key=replacement_key,
        default=default,
        raise_if_present=raise_if_present or False,
        option_removed=False,
    )


def removed(
    key: str,
    default: Any | None = None,
    raise_if_present: bool | None = True,
) -> Callable[[dict], dict]:
    """Log key as deprecated and fail the config validation.

    Expected behavior:
        - Outputs the appropriate error if key is detected and removed from
          support or raises an exception.
    """
    return _deprecated_or_removed(
        key,
        replacement_key=None,
        default=default,
        raise_if_present=raise_if_present or False,
        option_removed=True,
    )


def key_value_schemas(
    key: str,
    value_schemas: dict[Hashable, vol.Schema],
    default_schema: vol.Schema | None = None,
    default_description: str | None = None,
) -> Callable[[Any], dict[Hashable, Any]]:
    """Create a validator that validates based on a value for specific key.

    This gives better error messages.
    """

    def key_value_validator(value: Any) -> dict[Hashable, Any]:
        if not isinstance(value, dict):
            raise vol.Invalid("Expected a dictionary")

        key_value = value.get(key)

        if isinstance(key_value, Hashable) and key_value in value_schemas:
            return cast(dict[Hashable, Any], value_schemas[key_value](value))

        if default_schema:
            with contextlib.suppress(vol.Invalid):
                return cast(dict[Hashable, Any], default_schema(value))

        alternatives = ", ".join(str(alternative) for alternative in value_schemas)
        if default_description:
            alternatives = f"{alternatives}, {default_description}"
        raise vol.Invalid(
            f"Unexpected value for {key}: '{key_value}'. Expected {alternatives}"
        )

    return key_value_validator


# Validator helpers


def key_dependency(
    key: Hashable, dependency: Hashable
) -> Callable[[dict[Hashable, Any]], dict[Hashable, Any]]:
    """Validate that all dependencies exist for key."""

    def validator(value: dict[Hashable, Any]) -> dict[Hashable, Any]:
        """Test dependencies."""
        if not isinstance(value, dict):
            raise vol.Invalid("key dependencies require a dict")
        if key in value and dependency not in value:
            raise vol.Invalid(
                f'dependency violation - key "{key}" requires '
                f'key "{dependency}" to exist'
            )

        return value

    return validator


def custom_serializer(schema: Any) -> Any:
    """Serialize additional types for voluptuous_serialize."""
    from .. import data_entry_flow  # pylint: disable=import-outside-toplevel
    from . import selector  # pylint: disable=import-outside-toplevel

    if schema is positive_time_period_dict:
        return {"type": "positive_time_period_dict"}

    if schema is string:
        return {"type": "string"}

    if schema is boolean:
        return {"type": "boolean"}

    if isinstance(schema, data_entry_flow.section):
        return {
            "type": "expandable",
            "schema": voluptuous_serialize.convert(
                schema.schema, custom_serializer=custom_serializer
            ),
            "expanded": not schema.options["collapsed"],
        }

    if isinstance(schema, multi_select):
        return {"type": "multi_select", "options": schema.options}

    if isinstance(schema, selector.Selector):
        return schema.serialize()

    return voluptuous_serialize.UNSUPPORTED


def expand_condition_shorthand(value: Any | None) -> Any:
    """Expand boolean condition shorthand notations."""

    if not isinstance(value, dict) or CONF_CONDITIONS in value:
        return value

    for key, schema in (
        ("and", AND_CONDITION_SHORTHAND_SCHEMA),
        ("or", OR_CONDITION_SHORTHAND_SCHEMA),
        ("not", NOT_CONDITION_SHORTHAND_SCHEMA),
    ):
        try:
            schema(value)
            return {
                CONF_CONDITION: key,
                CONF_CONDITIONS: value[key],
                **{k: value[k] for k in value if k != key},
            }
        except vol.MultipleInvalid:
            pass

    if isinstance(value.get(CONF_CONDITION), list):
        try:
            CONDITION_SHORTHAND_SCHEMA(value)
            return {
                CONF_CONDITION: "and",
                CONF_CONDITIONS: value[CONF_CONDITION],
                **{k: value[k] for k in value if k != CONF_CONDITION},
            }
        except vol.MultipleInvalid:
            pass

    return value


# Schemas
def empty_config_schema(domain: str) -> Callable[[dict], dict]:
    """Return a config schema which logs if there are configuration parameters."""

    def validator(config: dict) -> dict:
        if config_domain := config.get(domain):
            get_integration_logger(__name__).error(
                (
                    "The %s integration does not support any configuration parameters, "
                    "got %s. Please remove the configuration parameters from your "
                    "configuration."
                ),
                domain,
                config_domain,
            )
        return config

    return validator


def _no_yaml_config_schema(
    domain: str,
    issue_base: str,
    translation_key: str,
    translation_placeholders: dict[str, str],
) -> Callable[[dict], dict]:
    """Return a config schema which logs if attempted to setup from YAML."""

    def raise_issue() -> None:
        # pylint: disable-next=import-outside-toplevel
        from .issue_registry import IssueSeverity, async_create_issue

        # HomeAssistantError is raised if called from the wrong thread
        with contextlib.suppress(HomeAssistantError):
            hass = async_get_hass()
            async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"{issue_base}_{domain}",
                is_fixable=False,
                issue_domain=domain,
                severity=IssueSeverity.ERROR,
                translation_key=translation_key,
                translation_placeholders={"domain": domain} | translation_placeholders,
            )

    def validator(config: dict) -> dict:
        if domain in config:
            get_integration_logger(__name__).error(
                (
                    "The %s integration does not support YAML setup, please remove it "
                    "from your configuration file"
                ),
                domain,
            )
            raise_issue()
        return config

    return validator


def config_entry_only_config_schema(domain: str) -> Callable[[dict], dict]:
    """Return a config schema which logs if attempted to setup from YAML.

    Use this when an integration's __init__.py defines setup or async_setup
    but setup from yaml is not supported.
    """

    return _no_yaml_config_schema(
        domain,
        "config_entry_only",
        "config_entry_only",
        {"add_integration": f"/config/integrations/dashboard/add?domain={domain}"},
    )


def platform_only_config_schema(domain: str) -> Callable[[dict], dict]:
    """Return a config schema which logs if attempted to setup from YAML.

    Use this when an integration's __init__.py defines setup or async_setup
    but setup from the integration key is not supported.
    """

    return _no_yaml_config_schema(
        domain,
        "platform_only",
        "platform_only",
        {},
    )


PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): string,
        vol.Optional(CONF_ENTITY_NAMESPACE): string,
        vol.Optional(CONF_SCAN_INTERVAL): time_period,
    }
)

PLATFORM_SCHEMA_BASE = PLATFORM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)

ENTITY_SERVICE_FIELDS = {
    # Either accept static entity IDs, a single dynamic template or a mixed list
    # of static and dynamic templates. While this could be solved with a single
    # complex template, handling it like this, keeps config validation useful.
    vol.Optional(ATTR_ENTITY_ID): vol.Any(
        comp_entity_ids, dynamic_template, vol.All(list, template_complex)
    ),
    vol.Optional(ATTR_DEVICE_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_AREA_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_FLOOR_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_LABEL_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
}

TARGET_SERVICE_FIELDS = {
    # Same as ENTITY_SERVICE_FIELDS but supports specifying entity by entity registry
    # ID.
    # Either accept static entity IDs, a single dynamic template or a mixed list
    # of static and dynamic templates. While this could be solved with a single
    # complex template, handling it like this, keeps config validation useful.
    vol.Optional(ATTR_ENTITY_ID): vol.Any(
        comp_entity_ids_or_uuids, dynamic_template, vol.All(list, template_complex)
    ),
    vol.Optional(ATTR_DEVICE_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_AREA_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_FLOOR_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
    vol.Optional(ATTR_LABEL_ID): vol.Any(
        ENTITY_MATCH_NONE, vol.All(ensure_list, [vol.Any(dynamic_template, str)])
    ),
}


_HAS_ENTITY_SERVICE_FIELD = has_at_least_one_key(*ENTITY_SERVICE_FIELDS)


def _make_entity_service_schema(schema: dict, extra: int) -> vol.Schema:
    """Create an entity service schema."""
    return vol.Schema(
        vol.All(
            vol.Schema(
                {
                    # The frontend stores data here. Don't use in core.
                    vol.Remove("metadata"): dict,
                    **schema,
                    **ENTITY_SERVICE_FIELDS,
                },
                extra=extra,
            ),
            _HAS_ENTITY_SERVICE_FIELD,
        )
    )


BASE_ENTITY_SCHEMA = _make_entity_service_schema({}, vol.PREVENT_EXTRA)


def make_entity_service_schema(
    schema: dict, *, extra: int = vol.PREVENT_EXTRA
) -> vol.Schema:
    """Create an entity service schema."""
    if not schema and extra == vol.PREVENT_EXTRA:
        # If the schema is empty and we don't allow extra keys, we can return
        # the base schema and avoid compiling a new schema which is the case
        # for ~50% of services.
        return BASE_ENTITY_SCHEMA
    return _make_entity_service_schema(schema, extra)


SCRIPT_CONVERSATION_RESPONSE_SCHEMA = vol.Any(template, None)


SCRIPT_VARIABLES_SCHEMA = vol.All(
    vol.Schema({str: template_complex}),
    # pylint: disable-next=unnecessary-lambda
    lambda val: script_variables_helper.ScriptVariables(val),
)


def script_action(value: Any) -> dict:
    """Validate a script action."""
    if not isinstance(value, dict):
        raise vol.Invalid("expected dictionary")

    try:
        action = determine_script_action(value)
    except ValueError as err:
        raise vol.Invalid(str(err)) from err

    return ACTION_TYPE_SCHEMAS[action](value)


SCRIPT_SCHEMA = vol.All(ensure_list, [script_action])

SCRIPT_ACTION_BASE_SCHEMA = {
    vol.Optional(CONF_ALIAS): string,
    vol.Optional(CONF_CONTINUE_ON_ERROR): boolean,
    vol.Optional(CONF_ENABLED): vol.Any(boolean, template),
}

EVENT_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_EVENT): string,
        vol.Optional(CONF_EVENT_DATA): vol.All(dict, template_complex),
        vol.Optional(CONF_EVENT_DATA_TEMPLATE): vol.All(dict, template_complex),
    }
)

SERVICE_SCHEMA = vol.All(
    vol.Schema(
        {
            **SCRIPT_ACTION_BASE_SCHEMA,
            vol.Exclusive(CONF_SERVICE, "service name"): vol.Any(
                service, dynamic_template
            ),
            vol.Exclusive(CONF_SERVICE_TEMPLATE, "service name"): vol.Any(
                service, dynamic_template
            ),
            vol.Optional(CONF_SERVICE_DATA): vol.Any(
                template, vol.All(dict, template_complex)
            ),
            vol.Optional(CONF_SERVICE_DATA_TEMPLATE): vol.Any(
                template, vol.All(dict, template_complex)
            ),
            vol.Optional(CONF_ENTITY_ID): comp_entity_ids,
            vol.Optional(CONF_TARGET): vol.Any(TARGET_SERVICE_FIELDS, dynamic_template),
            vol.Optional(CONF_RESPONSE_VARIABLE): str,
            # The frontend stores data here. Don't use in core.
            vol.Remove("metadata"): dict,
        }
    ),
    has_at_least_one_key(CONF_SERVICE, CONF_SERVICE_TEMPLATE),
)

NUMERIC_STATE_THRESHOLD_SCHEMA = vol.Any(
    vol.Coerce(float),
    vol.All(str, entity_domain(["input_number", "number", "sensor", "zone"])),
)

CONDITION_BASE_SCHEMA = {
    vol.Optional(CONF_ALIAS): string,
    vol.Optional(CONF_ENABLED): vol.Any(boolean, template),
}

NUMERIC_STATE_CONDITION_SCHEMA = vol.All(
    vol.Schema(
        {
            **CONDITION_BASE_SCHEMA,
            vol.Required(CONF_CONDITION): "numeric_state",
            vol.Required(CONF_ENTITY_ID): entity_ids_or_uuids,
            vol.Optional(CONF_ATTRIBUTE): str,
            CONF_BELOW: NUMERIC_STATE_THRESHOLD_SCHEMA,
            CONF_ABOVE: NUMERIC_STATE_THRESHOLD_SCHEMA,
            vol.Optional(CONF_VALUE_TEMPLATE): template,
        }
    ),
    has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

STATE_CONDITION_BASE_SCHEMA = {
    **CONDITION_BASE_SCHEMA,
    vol.Required(CONF_CONDITION): "state",
    vol.Required(CONF_ENTITY_ID): entity_ids_or_uuids,
    vol.Optional(CONF_MATCH, default=ENTITY_MATCH_ALL): vol.All(
        vol.Lower, vol.Any(ENTITY_MATCH_ALL, ENTITY_MATCH_ANY)
    ),
    vol.Optional(CONF_ATTRIBUTE): str,
    vol.Optional(CONF_FOR): positive_time_period_template,
    # To support use_trigger_value in automation
    # Deprecated 2016/04/25
    vol.Optional("from"): str,
}

STATE_CONDITION_STATE_SCHEMA = vol.Schema(
    {
        **STATE_CONDITION_BASE_SCHEMA,
        vol.Required(CONF_STATE): vol.Any(str, [str]),
    }
)

STATE_CONDITION_ATTRIBUTE_SCHEMA = vol.Schema(
    {
        **STATE_CONDITION_BASE_SCHEMA,
        vol.Required(CONF_STATE): match_all,
    }
)


def STATE_CONDITION_SCHEMA(value: Any) -> dict:
    """Validate a state condition."""
    if not isinstance(value, dict):
        raise vol.Invalid("Expected a dictionary")

    if CONF_ATTRIBUTE in value:
        validated: dict = STATE_CONDITION_ATTRIBUTE_SCHEMA(value)
    else:
        validated = STATE_CONDITION_STATE_SCHEMA(value)

    return key_dependency("for", "state")(validated)


SUN_CONDITION_SCHEMA = vol.All(
    vol.Schema(
        {
            **CONDITION_BASE_SCHEMA,
            vol.Required(CONF_CONDITION): "sun",
            vol.Optional("before"): sun_event,
            vol.Optional("before_offset"): time_period,
            vol.Optional("after"): vol.All(
                vol.Lower, vol.Any(SUN_EVENT_SUNSET, SUN_EVENT_SUNRISE)
            ),
            vol.Optional("after_offset"): time_period,
        }
    ),
    has_at_least_one_key("before", "after"),
)

TEMPLATE_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "template",
        vol.Required(CONF_VALUE_TEMPLATE): template,
    }
)

TIME_CONDITION_SCHEMA = vol.All(
    vol.Schema(
        {
            **CONDITION_BASE_SCHEMA,
            vol.Required(CONF_CONDITION): "time",
            vol.Optional("before"): vol.Any(
                time, vol.All(str, entity_domain(["input_datetime", "sensor"]))
            ),
            vol.Optional("after"): vol.Any(
                time, vol.All(str, entity_domain(["input_datetime", "sensor"]))
            ),
            vol.Optional("weekday"): weekdays,
        }
    ),
    has_at_least_one_key("before", "after", "weekday"),
)

TRIGGER_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "trigger",
        vol.Required(CONF_ID): vol.All(ensure_list, [string]),
    }
)

ZONE_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "zone",
        vol.Required(CONF_ENTITY_ID): entity_ids,
        vol.Required("zone"): entity_ids,
        # To support use_trigger_value in automation
        # Deprecated 2016/04/25
        vol.Optional("event"): vol.Any("enter", "leave"),
    }
)

AND_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "and",
        vol.Required(CONF_CONDITIONS): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

AND_CONDITION_SHORTHAND_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required("and"): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

OR_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "or",
        vol.Required(CONF_CONDITIONS): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

OR_CONDITION_SHORTHAND_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required("or"): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

NOT_CONDITION_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "not",
        vol.Required(CONF_CONDITIONS): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

NOT_CONDITION_SHORTHAND_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required("not"): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

DEVICE_CONDITION_BASE_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): str,
        vol.Remove("metadata"): dict,
    }
)

DEVICE_CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)

dynamic_template_condition_action = vol.All(
    # Wrap a shorthand template condition in a template condition
    dynamic_template,
    lambda config: {
        CONF_VALUE_TEMPLATE: config,
        CONF_CONDITION: "template",
    },
)

CONDITION_SHORTHAND_SCHEMA = vol.Schema(
    {
        **CONDITION_BASE_SCHEMA,
        vol.Required(CONF_CONDITION): vol.All(
            ensure_list,
            # pylint: disable-next=unnecessary-lambda
            [lambda value: CONDITION_SCHEMA(value)],
        ),
    }
)

CONDITION_SCHEMA: vol.Schema = vol.Schema(
    vol.Any(
        vol.All(
            expand_condition_shorthand,
            key_value_schemas(
                CONF_CONDITION,
                {
                    "and": AND_CONDITION_SCHEMA,
                    "device": DEVICE_CONDITION_SCHEMA,
                    "not": NOT_CONDITION_SCHEMA,
                    "numeric_state": NUMERIC_STATE_CONDITION_SCHEMA,
                    "or": OR_CONDITION_SCHEMA,
                    "state": STATE_CONDITION_SCHEMA,
                    "sun": SUN_CONDITION_SCHEMA,
                    "template": TEMPLATE_CONDITION_SCHEMA,
                    "time": TIME_CONDITION_SCHEMA,
                    "trigger": TRIGGER_CONDITION_SCHEMA,
                    "zone": ZONE_CONDITION_SCHEMA,
                },
            ),
        ),
        dynamic_template_condition_action,
    )
)

CONDITIONS_SCHEMA = vol.All(ensure_list, [CONDITION_SCHEMA])

dynamic_template_condition_action = vol.All(
    # Wrap a shorthand template condition action in a template condition
    vol.Schema(
        {**CONDITION_BASE_SCHEMA, vol.Required(CONF_CONDITION): dynamic_template}
    ),
    lambda config: {
        **config,
        CONF_VALUE_TEMPLATE: config[CONF_CONDITION],
        CONF_CONDITION: "template",
    },
)


CONDITION_ACTION_SCHEMA: vol.Schema = vol.Schema(
    vol.All(
        expand_condition_shorthand,
        key_value_schemas(
            CONF_CONDITION,
            {
                "and": AND_CONDITION_SCHEMA,
                "device": DEVICE_CONDITION_SCHEMA,
                "not": NOT_CONDITION_SCHEMA,
                "numeric_state": NUMERIC_STATE_CONDITION_SCHEMA,
                "or": OR_CONDITION_SCHEMA,
                "state": STATE_CONDITION_SCHEMA,
                "sun": SUN_CONDITION_SCHEMA,
                "template": TEMPLATE_CONDITION_SCHEMA,
                "time": TIME_CONDITION_SCHEMA,
                "trigger": TRIGGER_CONDITION_SCHEMA,
                "zone": ZONE_CONDITION_SCHEMA,
            },
            dynamic_template_condition_action,
            "a list of conditions or a valid template",
        ),
    )
)

TRIGGER_BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ALIAS): str,
        vol.Required(CONF_PLATFORM): str,
        vol.Optional(CONF_ID): str,
        vol.Optional(CONF_VARIABLES): SCRIPT_VARIABLES_SCHEMA,
        vol.Optional(CONF_ENABLED): vol.Any(boolean, template),
    }
)


_base_trigger_validator_schema = TRIGGER_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


# This is first round of validation, we don't want to process the config here already,
# just ensure basics as platform and ID are there.
def _base_trigger_validator(value: Any) -> Any:
    _base_trigger_validator_schema(value)
    return value


TRIGGER_SCHEMA = vol.All(ensure_list, [_base_trigger_validator])

_SCRIPT_DELAY_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_DELAY): positive_time_period_template,
    }
)

_SCRIPT_WAIT_TEMPLATE_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_WAIT_TEMPLATE): template,
        vol.Optional(CONF_TIMEOUT): positive_time_period_template,
        vol.Optional(CONF_CONTINUE_ON_TIMEOUT): boolean,
    }
)

DEVICE_ACTION_BASE_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_DEVICE_ID): string,
        vol.Required(CONF_DOMAIN): str,
        vol.Remove("metadata"): dict,
    }
)

DEVICE_ACTION_SCHEMA = DEVICE_ACTION_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)

_SCRIPT_SCENE_SCHEMA = vol.Schema(
    {**SCRIPT_ACTION_BASE_SCHEMA, vol.Required(CONF_SCENE): entity_domain("scene")}
)

_SCRIPT_REPEAT_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_REPEAT): vol.All(
            {
                vol.Exclusive(CONF_COUNT, "repeat"): vol.Any(vol.Coerce(int), template),
                vol.Exclusive(CONF_FOR_EACH, "repeat"): vol.Any(
                    dynamic_template, vol.All(list, template_complex)
                ),
                vol.Exclusive(CONF_WHILE, "repeat"): vol.All(
                    ensure_list, [CONDITION_SCHEMA]
                ),
                vol.Exclusive(CONF_UNTIL, "repeat"): vol.All(
                    ensure_list, [CONDITION_SCHEMA]
                ),
                vol.Required(CONF_SEQUENCE): SCRIPT_SCHEMA,
            },
            has_at_least_one_key(CONF_COUNT, CONF_FOR_EACH, CONF_WHILE, CONF_UNTIL),
        ),
    }
)

_SCRIPT_CHOOSE_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_CHOOSE): vol.All(
            ensure_list,
            [
                {
                    vol.Optional(CONF_ALIAS): string,
                    vol.Required(CONF_CONDITIONS): vol.All(
                        ensure_list, [CONDITION_SCHEMA]
                    ),
                    vol.Required(CONF_SEQUENCE): SCRIPT_SCHEMA,
                }
            ],
        ),
        vol.Optional(CONF_DEFAULT): SCRIPT_SCHEMA,
    }
)

_SCRIPT_WAIT_FOR_TRIGGER_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_WAIT_FOR_TRIGGER): TRIGGER_SCHEMA,
        vol.Optional(CONF_TIMEOUT): positive_time_period_template,
        vol.Optional(CONF_CONTINUE_ON_TIMEOUT): boolean,
    }
)

_SCRIPT_IF_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_IF): vol.All(ensure_list, [CONDITION_SCHEMA]),
        vol.Required(CONF_THEN): SCRIPT_SCHEMA,
        vol.Optional(CONF_ELSE): SCRIPT_SCHEMA,
    }
)

_SCRIPT_SET_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_VARIABLES): SCRIPT_VARIABLES_SCHEMA,
    }
)

_SCRIPT_SET_CONVERSATION_RESPONSE_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(
            CONF_SET_CONVERSATION_RESPONSE
        ): SCRIPT_CONVERSATION_RESPONSE_SCHEMA,
    }
)

_SCRIPT_STOP_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_STOP): vol.Any(None, string),
        vol.Exclusive(CONF_ERROR, "error_or_response"): boolean,
        vol.Exclusive(
            CONF_RESPONSE_VARIABLE,
            "error_or_response",
            msg="not allowed to add a response to an error stop action",
        ): str,
    }
)

_SCRIPT_SEQUENCE_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_SEQUENCE): SCRIPT_SCHEMA,
    }
)

_parallel_sequence_action = vol.All(
    # Wrap a shorthand sequences in a parallel action
    SCRIPT_SCHEMA,
    lambda config: {
        CONF_SEQUENCE: config,
    },
)

_SCRIPT_PARALLEL_SCHEMA = vol.Schema(
    {
        **SCRIPT_ACTION_BASE_SCHEMA,
        vol.Required(CONF_PARALLEL): vol.All(
            ensure_list, [vol.Any(_SCRIPT_SEQUENCE_SCHEMA, _parallel_sequence_action)]
        ),
    }
)


SCRIPT_ACTION_ACTIVATE_SCENE = "scene"
SCRIPT_ACTION_CALL_SERVICE = "call_service"
SCRIPT_ACTION_CHECK_CONDITION = "condition"
SCRIPT_ACTION_CHOOSE = "choose"
SCRIPT_ACTION_DELAY = "delay"
SCRIPT_ACTION_DEVICE_AUTOMATION = "device"
SCRIPT_ACTION_FIRE_EVENT = "event"
SCRIPT_ACTION_IF = "if"
SCRIPT_ACTION_PARALLEL = "parallel"
SCRIPT_ACTION_REPEAT = "repeat"
SCRIPT_ACTION_SEQUENCE = "sequence"
SCRIPT_ACTION_SET_CONVERSATION_RESPONSE = "set_conversation_response"
SCRIPT_ACTION_STOP = "stop"
SCRIPT_ACTION_VARIABLES = "variables"
SCRIPT_ACTION_WAIT_FOR_TRIGGER = "wait_for_trigger"
SCRIPT_ACTION_WAIT_TEMPLATE = "wait_template"


ACTIONS_MAP = {
    CONF_DELAY: SCRIPT_ACTION_DELAY,
    CONF_WAIT_TEMPLATE: SCRIPT_ACTION_WAIT_TEMPLATE,
    CONF_CONDITION: SCRIPT_ACTION_CHECK_CONDITION,
    "and": SCRIPT_ACTION_CHECK_CONDITION,
    "or": SCRIPT_ACTION_CHECK_CONDITION,
    "not": SCRIPT_ACTION_CHECK_CONDITION,
    CONF_EVENT: SCRIPT_ACTION_FIRE_EVENT,
    CONF_DEVICE_ID: SCRIPT_ACTION_DEVICE_AUTOMATION,
    CONF_SCENE: SCRIPT_ACTION_ACTIVATE_SCENE,
    CONF_REPEAT: SCRIPT_ACTION_REPEAT,
    CONF_CHOOSE: SCRIPT_ACTION_CHOOSE,
    CONF_WAIT_FOR_TRIGGER: SCRIPT_ACTION_WAIT_FOR_TRIGGER,
    CONF_VARIABLES: SCRIPT_ACTION_VARIABLES,
    CONF_IF: SCRIPT_ACTION_IF,
    CONF_SERVICE: SCRIPT_ACTION_CALL_SERVICE,
    CONF_SERVICE_TEMPLATE: SCRIPT_ACTION_CALL_SERVICE,
    CONF_STOP: SCRIPT_ACTION_STOP,
    CONF_PARALLEL: SCRIPT_ACTION_PARALLEL,
    CONF_SEQUENCE: SCRIPT_ACTION_SEQUENCE,
    CONF_SET_CONVERSATION_RESPONSE: SCRIPT_ACTION_SET_CONVERSATION_RESPONSE,
}

ACTIONS_SET = set(ACTIONS_MAP)


def determine_script_action(action: dict[str, Any]) -> str:
    """Determine action type."""
    if not (actions := ACTIONS_SET.intersection(action)):
        raise ValueError("Unable to determine action")
    if len(actions) > 1:
        # Ambiguous action, select the first one in the
        # order of the ACTIONS_MAP
        for action_key, _script_action in ACTIONS_MAP.items():
            if action_key in actions:
                return _script_action
    return ACTIONS_MAP[actions.pop()]


ACTION_TYPE_SCHEMAS: dict[str, Callable[[Any], dict]] = {
    SCRIPT_ACTION_ACTIVATE_SCENE: _SCRIPT_SCENE_SCHEMA,
    SCRIPT_ACTION_CALL_SERVICE: SERVICE_SCHEMA,
    SCRIPT_ACTION_CHECK_CONDITION: CONDITION_ACTION_SCHEMA,
    SCRIPT_ACTION_CHOOSE: _SCRIPT_CHOOSE_SCHEMA,
    SCRIPT_ACTION_DELAY: _SCRIPT_DELAY_SCHEMA,
    SCRIPT_ACTION_DEVICE_AUTOMATION: DEVICE_ACTION_SCHEMA,
    SCRIPT_ACTION_FIRE_EVENT: EVENT_SCHEMA,
    SCRIPT_ACTION_IF: _SCRIPT_IF_SCHEMA,
    SCRIPT_ACTION_PARALLEL: _SCRIPT_PARALLEL_SCHEMA,
    SCRIPT_ACTION_REPEAT: _SCRIPT_REPEAT_SCHEMA,
    SCRIPT_ACTION_SEQUENCE: _SCRIPT_SEQUENCE_SCHEMA,
    SCRIPT_ACTION_SET_CONVERSATION_RESPONSE: _SCRIPT_SET_CONVERSATION_RESPONSE_SCHEMA,
    SCRIPT_ACTION_STOP: _SCRIPT_STOP_SCHEMA,
    SCRIPT_ACTION_VARIABLES: _SCRIPT_SET_SCHEMA,
    SCRIPT_ACTION_WAIT_FOR_TRIGGER: _SCRIPT_WAIT_FOR_TRIGGER_SCHEMA,
    SCRIPT_ACTION_WAIT_TEMPLATE: _SCRIPT_WAIT_TEMPLATE_SCHEMA,
}


currency = vol.In(
    currencies.ACTIVE_CURRENCIES, msg="invalid ISO 4217 formatted currency"
)

historic_currency = vol.In(
    currencies.HISTORIC_CURRENCIES, msg="invalid ISO 4217 formatted historic currency"
)

country = vol.In(COUNTRIES, msg="invalid ISO 3166 formatted country")

language = vol.In(LANGUAGES, msg="invalid RFC 5646 formatted language")
