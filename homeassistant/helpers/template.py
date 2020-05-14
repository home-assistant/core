"""Template helper methods for rendering strings with Home Assistant data."""
import base64
import collections.abc
from datetime import datetime
from functools import wraps
import json
import logging
import math
import random
import re
from typing import Any, Dict, Iterable, List, Optional, Union

import jinja2
from jinja2 import contextfilter, contextfunction
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2.utils import Namespace  # type: ignore

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    LENGTH_METERS,
    MATCH_ALL,
    STATE_UNKNOWN,
)
from homeassistant.core import State, callback, split_entity_id, valid_entity_id
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import location as loc_helper
from homeassistant.helpers.typing import HomeAssistantType, TemplateVarsType
from homeassistant.loader import bind_hass
from homeassistant.util import convert, dt as dt_util, location as loc_util
from homeassistant.util.async_ import run_callback_threadsafe

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any

_LOGGER = logging.getLogger(__name__)
_SENTINEL = object()
DATE_STR_FORMAT = "%Y-%m-%d %H:%M:%S"

_RENDER_INFO = "template.render_info"
_ENVIRONMENT = "template.environment"

_RE_NONE_ENTITIES = re.compile(r"distance\(|closest\(", re.I | re.M)
_RE_GET_ENTITIES = re.compile(
    r"(?:(?:states\.|(?P<func>is_state|is_state_attr|state_attr|states|expand)"
    r"\((?:[\ \'\"]?))(?P<entity_id>[\w]+\.[\w]+)|(?P<variable>[\w]+))",
    re.I | re.M,
)
_RE_JINJA_DELIMITERS = re.compile(r"\{%|\{\{")


@bind_hass
def attach(hass: HomeAssistantType, obj: Any) -> None:
    """Recursively attach hass to all template instances in list and dict."""
    if isinstance(obj, list):
        for child in obj:
            attach(hass, child)
    elif isinstance(obj, dict):
        for child in obj.values():
            attach(hass, child)
    elif isinstance(obj, Template):
        obj.hass = hass


def render_complex(value: Any, variables: TemplateVarsType = None) -> Any:
    """Recursive template creator helper function."""
    if isinstance(value, list):
        return [render_complex(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: render_complex(item, variables) for key, item in value.items()}
    if isinstance(value, Template):
        return value.async_render(variables)
    return value


def extract_entities(
    hass: HomeAssistantType,
    template: Optional[str],
    variables: Optional[Dict[str, Any]] = None,
) -> Union[str, List[str]]:
    """Extract all entities for state_changed listener from template string."""
    if template is None or _RE_JINJA_DELIMITERS.search(template) is None:
        return []

    if _RE_NONE_ENTITIES.search(template):
        return MATCH_ALL

    extraction_final = []

    for result in _RE_GET_ENTITIES.finditer(template):
        if (
            result.group("entity_id") == "trigger.entity_id"
            and variables
            and "trigger" in variables
            and "entity_id" in variables["trigger"]
        ):
            extraction_final.append(variables["trigger"]["entity_id"])
        elif result.group("entity_id"):
            if result.group("func") == "expand":
                for entity in expand(hass, result.group("entity_id")):
                    extraction_final.append(entity.entity_id)

            extraction_final.append(result.group("entity_id"))

        if (
            variables
            and result.group("variable") in variables
            and isinstance(variables[result.group("variable")], str)
            and valid_entity_id(variables[result.group("variable")])
        ):
            extraction_final.append(variables[result.group("variable")])

    if extraction_final:
        return list(set(extraction_final))
    return MATCH_ALL


def _true(arg: Any) -> bool:
    return True


class RenderInfo:
    """Holds information about a template render."""

    def __init__(self, template):
        """Initialise."""
        self.template = template
        # Will be set sensibly once frozen.
        self.filter_lifecycle = _true
        self._result = None
        self._exception = None
        self._all_states = False
        self._domains = []
        self._entities = []

    def filter(self, entity_id: str) -> bool:
        """Template should re-render if the state changes."""
        return entity_id in self._entities

    def _filter_lifecycle(self, entity_id: str) -> bool:
        """Template should re-render if the state changes."""
        return (
            split_entity_id(entity_id)[0] in self._domains
            or entity_id in self._entities
        )

    @property
    def result(self) -> str:
        """Results of the template computation."""
        if self._exception is not None:
            raise self._exception
        return self._result

    def _freeze(self) -> None:
        self._entities = frozenset(self._entities)
        if self._all_states:
            # Leave lifecycle_filter as True
            del self._domains
        elif not self._domains:
            del self._domains
            self.filter_lifecycle = self.filter
        else:
            self._domains = frozenset(self._domains)
            self.filter_lifecycle = self._filter_lifecycle


class Template:
    """Class to hold a template and manage caching and rendering."""

    def __init__(self, template, hass=None):
        """Instantiate a template."""
        if not isinstance(template, str):
            raise TypeError("Expected template to be a string")

        self.template: str = template
        self._compiled_code = None
        self._compiled = None
        self.hass = hass

    @property
    def _env(self):
        if self.hass is None:
            return _NO_HASS_ENV
        ret = self.hass.data.get(_ENVIRONMENT)
        if ret is None:
            ret = self.hass.data[_ENVIRONMENT] = TemplateEnvironment(self.hass)
        return ret

    def ensure_valid(self):
        """Return if template is valid."""
        if self._compiled_code is not None:
            return

        try:
            self._compiled_code = self._env.compile(self.template)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise TemplateError(err)

    def extract_entities(
        self, variables: Optional[Dict[str, Any]] = None
    ) -> Union[str, List[str]]:
        """Extract all entities for state_changed listener."""
        return extract_entities(self.hass, self.template, variables)

    def render(self, variables: TemplateVarsType = None, **kwargs: Any) -> str:
        """Render given template."""
        if variables is not None:
            kwargs.update(variables)

        return run_callback_threadsafe(
            self.hass.loop, self.async_render, kwargs
        ).result()

    @callback
    def async_render(self, variables: TemplateVarsType = None, **kwargs: Any) -> str:
        """Render given template.

        This method must be run in the event loop.
        """
        compiled = self._compiled or self._ensure_compiled()

        if variables is not None:
            kwargs.update(variables)

        try:
            return compiled.render(kwargs).strip()
        except jinja2.TemplateError as err:
            raise TemplateError(err)

    @callback
    def async_render_to_info(
        self, variables: TemplateVarsType = None, **kwargs: Any
    ) -> RenderInfo:
        """Render the template and collect an entity filter."""
        assert self.hass and _RENDER_INFO not in self.hass.data
        render_info = self.hass.data[_RENDER_INFO] = RenderInfo(self)
        # pylint: disable=protected-access
        try:
            render_info._result = self.async_render(variables, **kwargs)
        except TemplateError as ex:
            render_info._exception = ex
        finally:
            del self.hass.data[_RENDER_INFO]
            render_info._freeze()
        return render_info

    def render_with_possible_json_value(self, value, error_value=_SENTINEL):
        """Render template with value exposed.

        If valid JSON will expose value_json too.
        """
        return run_callback_threadsafe(
            self.hass.loop,
            self.async_render_with_possible_json_value,
            value,
            error_value,
        ).result()

    @callback
    def async_render_with_possible_json_value(
        self, value, error_value=_SENTINEL, variables=None
    ):
        """Render template with value exposed.

        If valid JSON will expose value_json too.

        This method must be run in the event loop.
        """
        if self._compiled is None:
            self._ensure_compiled()

        variables = dict(variables or {})
        variables["value"] = value

        try:
            variables["value_json"] = json.loads(value)
        except (ValueError, TypeError):
            pass

        try:
            return self._compiled.render(variables).strip()
        except jinja2.TemplateError as ex:
            if error_value is _SENTINEL:
                _LOGGER.error(
                    "Error parsing value: %s (value: %s, template: %s)",
                    ex,
                    value,
                    self.template,
                )
            return value if error_value is _SENTINEL else error_value

    def _ensure_compiled(self):
        """Bind a template to a specific hass instance."""
        self.ensure_valid()

        assert self.hass is not None, "hass variable not set on template"

        env = self._env

        self._compiled = jinja2.Template.from_code(
            env, self._compiled_code, env.globals, None
        )

        return self._compiled

    def __eq__(self, other):
        """Compare template with another."""
        return (
            self.__class__ == other.__class__
            and self.template == other.template
            and self.hass == other.hass
        )

    def __hash__(self) -> int:
        """Hash code for template."""
        return hash(self.template)

    def __repr__(self) -> str:
        """Representation of Template."""
        return 'Template("' + self.template + '")'


class AllStates:
    """Class to expose all HA states as attributes."""

    def __init__(self, hass):
        """Initialize all states."""
        self._hass = hass

    def __getattr__(self, name):
        """Return the domain state."""
        if "." in name:
            if not valid_entity_id(name):
                raise TemplateError(f"Invalid entity ID '{name}'")
            return _get_state(self._hass, name)
        if not valid_entity_id(f"{name}.entity"):
            raise TemplateError(f"Invalid domain name '{name}'")
        return DomainStates(self._hass, name)

    def _collect_all(self) -> None:
        render_info = self._hass.data.get(_RENDER_INFO)
        if render_info is not None:
            # pylint: disable=protected-access
            render_info._all_states = True

    def __iter__(self):
        """Return all states."""
        self._collect_all()
        return iter(
            _wrap_state(self._hass, state)
            for state in sorted(
                self._hass.states.async_all(), key=lambda state: state.entity_id
            )
        )

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_all()
        return len(self._hass.states.async_entity_ids())

    def __call__(self, entity_id):
        """Return the states."""
        state = _get_state(self._hass, entity_id)
        return STATE_UNKNOWN if state is None else state.state

    def __repr__(self) -> str:
        """Representation of All States."""
        return "<template AllStates>"


class DomainStates:
    """Class to expose a specific HA domain as attributes."""

    def __init__(self, hass, domain):
        """Initialize the domain states."""
        self._hass = hass
        self._domain = domain

    def __getattr__(self, name):
        """Return the states."""
        entity_id = f"{self._domain}.{name}"
        if not valid_entity_id(entity_id):
            raise TemplateError(f"Invalid entity ID '{entity_id}'")
        return _get_state(self._hass, entity_id)

    def _collect_domain(self) -> None:
        entity_collect = self._hass.data.get(_RENDER_INFO)
        if entity_collect is not None:
            # pylint: disable=protected-access
            entity_collect._domains.append(self._domain)

    def __iter__(self):
        """Return the iteration over all the states."""
        self._collect_domain()
        return iter(
            sorted(
                (
                    _wrap_state(self._hass, state)
                    for state in self._hass.states.async_all()
                    if state.domain == self._domain
                ),
                key=lambda state: state.entity_id,
            )
        )

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_domain()
        return len(self._hass.states.async_entity_ids(self._domain))

    def __repr__(self) -> str:
        """Representation of Domain States."""
        return f"<template DomainStates('{self._domain}')>"


class TemplateState(State):
    """Class to represent a state object in a template."""

    # Inheritance is done so functions that check against State keep working
    # pylint: disable=super-init-not-called
    def __init__(self, hass, state):
        """Initialize template state."""
        self._hass = hass
        self._state = state

    def _access_state(self):
        state = object.__getattribute__(self, "_state")
        hass = object.__getattribute__(self, "_hass")

        _collect_state(hass, state.entity_id)
        return state

    @property
    def state_with_unit(self) -> str:
        """Return the state concatenated with the unit if available."""
        state = object.__getattribute__(self, "_access_state")()
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit is None:
            return state.state
        return f"{state.state} {unit}"

    def __getattribute__(self, name):
        """Return an attribute of the state."""
        # This one doesn't count as an access of the state
        # since we either found it by looking direct for the ID
        # or got it off an iterator.
        if name == "entity_id" or name in object.__dict__:
            state = object.__getattribute__(self, "_state")
            return getattr(state, name)
        if name in TemplateState.__dict__:
            return object.__getattribute__(self, name)
        state = object.__getattribute__(self, "_access_state")()
        return getattr(state, name)

    def __repr__(self) -> str:
        """Representation of Template State."""
        state = object.__getattribute__(self, "_access_state")()
        rep = state.__repr__()
        return f"<template {rep[1:]}"


def _collect_state(hass: HomeAssistantType, entity_id: str) -> None:
    entity_collect = hass.data.get(_RENDER_INFO)
    if entity_collect is not None:
        # pylint: disable=protected-access
        entity_collect._entities.append(entity_id)


def _wrap_state(
    hass: HomeAssistantType, state: Optional[State]
) -> Optional[TemplateState]:
    """Wrap a state."""
    return None if state is None else TemplateState(hass, state)


def _get_state(hass: HomeAssistantType, entity_id: str) -> Optional[TemplateState]:
    state = hass.states.get(entity_id)
    if state is None:
        # Only need to collect if none, if not none collect first actual
        # access to the state properties in the state wrapper.
        _collect_state(hass, entity_id)
        return None
    return _wrap_state(hass, state)


def _resolve_state(
    hass: HomeAssistantType, entity_id_or_state: Any
) -> Union[State, TemplateState, None]:
    """Return state or entity_id if given."""
    if isinstance(entity_id_or_state, State):
        return entity_id_or_state
    if isinstance(entity_id_or_state, str):
        return _get_state(hass, entity_id_or_state)
    return None


def expand(hass: HomeAssistantType, *args: Any) -> Iterable[State]:
    """Expand out any groups into entity states."""
    search = list(args)
    found = {}
    while search:
        entity = search.pop()
        if isinstance(entity, str):
            entity_id = entity
            entity = _get_state(hass, entity)
            if entity is None:
                continue
        elif isinstance(entity, State):
            entity_id = entity.entity_id
        elif isinstance(entity, collections.abc.Iterable):
            search += entity
            continue
        else:
            # ignore other types
            continue

        # pylint: disable=import-outside-toplevel
        from homeassistant.components import group

        if split_entity_id(entity_id)[0] == group.DOMAIN:
            # Collect state will be called in here since it's wrapped
            group_entities = entity.attributes.get(ATTR_ENTITY_ID)
            if group_entities:
                search += group_entities
        else:
            found[entity_id] = entity
    return sorted(found.values(), key=lambda a: a.entity_id)


def closest(hass, *args):
    """Find closest entity.

    Closest to home:
        closest(states)
        closest(states.device_tracker)
        closest('group.children')
        closest(states.group.children)

    Closest to a point:
        closest(23.456, 23.456, 'group.children')
        closest('zone.school', 'group.children')
        closest(states.zone.school, 'group.children')

    As a filter:
        states | closest
        states.device_tracker | closest
        ['group.children', states.device_tracker] | closest
        'group.children' | closest(23.456, 23.456)
        states.device_tracker | closest('zone.school')
        'group.children' | closest(states.zone.school)

    """
    if len(args) == 1:
        latitude = hass.config.latitude
        longitude = hass.config.longitude
        entities = args[0]

    elif len(args) == 2:
        point_state = _resolve_state(hass, args[0])

        if point_state is None:
            _LOGGER.warning("Closest:Unable to find state %s", args[0])
            return None
        if not loc_helper.has_location(point_state):
            _LOGGER.warning(
                "Closest:State does not contain valid location: %s", point_state
            )
            return None

        latitude = point_state.attributes.get(ATTR_LATITUDE)
        longitude = point_state.attributes.get(ATTR_LONGITUDE)

        entities = args[1]

    else:
        latitude = convert(args[0], float)
        longitude = convert(args[1], float)

        if latitude is None or longitude is None:
            _LOGGER.warning(
                "Closest:Received invalid coordinates: %s, %s", args[0], args[1]
            )
            return None

        entities = args[2]

    states = expand(hass, entities)

    # state will already be wrapped here
    return loc_helper.closest(latitude, longitude, states)


def closest_filter(hass, *args):
    """Call closest as a filter. Need to reorder arguments."""
    new_args = list(args[1:])
    new_args.append(args[0])
    return closest(hass, *new_args)


def distance(hass, *args):
    """Calculate distance.

    Will calculate distance from home to a point or between points.
    Points can be passed in using state objects or lat/lng coordinates.
    """
    locations = []

    to_process = list(args)

    while to_process:
        value = to_process.pop(0)
        point_state = _resolve_state(hass, value)

        if point_state is None:
            # We expect this and next value to be lat&lng
            if not to_process:
                _LOGGER.warning(
                    "Distance:Expected latitude and longitude, got %s", value
                )
                return None

            value_2 = to_process.pop(0)
            latitude = convert(value, float)
            longitude = convert(value_2, float)

            if latitude is None or longitude is None:
                _LOGGER.warning(
                    "Distance:Unable to process latitude and longitude: %s, %s",
                    value,
                    value_2,
                )
                return None

        else:
            if not loc_helper.has_location(point_state):
                _LOGGER.warning(
                    "distance:State does not contain valid location: %s", point_state
                )
                return None

            latitude = point_state.attributes.get(ATTR_LATITUDE)
            longitude = point_state.attributes.get(ATTR_LONGITUDE)

        locations.append((latitude, longitude))

    if len(locations) == 1:
        return hass.config.distance(*locations[0])

    return hass.config.units.length(
        loc_util.distance(*locations[0] + locations[1]), LENGTH_METERS
    )


def is_state(hass: HomeAssistantType, entity_id: str, state: State) -> bool:
    """Test if a state is a specific value."""
    state_obj = _get_state(hass, entity_id)
    return state_obj is not None and state_obj.state == state


def is_state_attr(hass, entity_id, name, value):
    """Test if a state's attribute is a specific value."""
    attr = state_attr(hass, entity_id, name)
    return attr is not None and attr == value


def state_attr(hass, entity_id, name):
    """Get a specific attribute from a state."""
    state_obj = _get_state(hass, entity_id)
    if state_obj is not None:
        return state_obj.attributes.get(name)
    return None


def forgiving_round(value, precision=0, method="common"):
    """Round accepted strings."""
    try:
        # support rounding methods like jinja
        multiplier = float(10 ** precision)
        if method == "ceil":
            value = math.ceil(float(value) * multiplier) / multiplier
        elif method == "floor":
            value = math.floor(float(value) * multiplier) / multiplier
        elif method == "half":
            value = round(float(value) * 2) / 2
        else:
            # if method is common or something else, use common rounding
            value = round(float(value), precision)
        return int(value) if precision == 0 else value
    except (ValueError, TypeError):
        # If value can't be converted to float
        return value


def multiply(value, amount):
    """Filter to convert value to float and multiply it."""
    try:
        return float(value) * amount
    except (ValueError, TypeError):
        # If value can't be converted to float
        return value


def logarithm(value, base=math.e):
    """Filter to get logarithm of the value with a specific base."""
    try:
        return math.log(float(value), float(base))
    except (ValueError, TypeError):
        return value


def sine(value):
    """Filter to get sine of the value."""
    try:
        return math.sin(float(value))
    except (ValueError, TypeError):
        return value


def cosine(value):
    """Filter to get cosine of the value."""
    try:
        return math.cos(float(value))
    except (ValueError, TypeError):
        return value


def tangent(value):
    """Filter to get tangent of the value."""
    try:
        return math.tan(float(value))
    except (ValueError, TypeError):
        return value


def arc_sine(value):
    """Filter to get arc sine of the value."""
    try:
        return math.asin(float(value))
    except (ValueError, TypeError):
        return value


def arc_cosine(value):
    """Filter to get arc cosine of the value."""
    try:
        return math.acos(float(value))
    except (ValueError, TypeError):
        return value


def arc_tangent(value):
    """Filter to get arc tangent of the value."""
    try:
        return math.atan(float(value))
    except (ValueError, TypeError):
        return value


def arc_tangent2(*args):
    """Filter to calculate four quadrant arc tangent of y / x."""
    try:
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]

        return math.atan2(float(args[0]), float(args[1]))
    except (ValueError, TypeError):
        return args


def square_root(value):
    """Filter to get square root of the value."""
    try:
        return math.sqrt(float(value))
    except (ValueError, TypeError):
        return value


def timestamp_custom(value, date_format=DATE_STR_FORMAT, local=True):
    """Filter to convert given timestamp to format."""
    try:
        date = dt_util.utc_from_timestamp(value)

        if local:
            date = dt_util.as_local(date)

        return date.strftime(date_format)
    except (ValueError, TypeError):
        # If timestamp can't be converted
        return value


def timestamp_local(value):
    """Filter to convert given timestamp to local date/time."""
    try:
        return dt_util.as_local(dt_util.utc_from_timestamp(value)).strftime(
            DATE_STR_FORMAT
        )
    except (ValueError, TypeError):
        # If timestamp can't be converted
        return value


def timestamp_utc(value):
    """Filter to convert given timestamp to UTC date/time."""
    try:
        return dt_util.utc_from_timestamp(value).strftime(DATE_STR_FORMAT)
    except (ValueError, TypeError):
        # If timestamp can't be converted
        return value


def forgiving_as_timestamp(value):
    """Try to convert value to timestamp."""
    try:
        return dt_util.as_timestamp(value)
    except (ValueError, TypeError):
        return None


def strptime(string, fmt):
    """Parse a time string to datetime."""
    try:
        return datetime.strptime(string, fmt)
    except (ValueError, AttributeError):
        return string


def fail_when_undefined(value):
    """Filter to force a failure when the value is undefined."""
    if isinstance(value, jinja2.Undefined):
        value()
    return value


def forgiving_float(value):
    """Try to convert value to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


def regex_match(value, find="", ignorecase=False):
    """Match value using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.I if ignorecase else 0
    return bool(re.match(find, value, flags))


def regex_replace(value="", find="", replace="", ignorecase=False):
    """Replace using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.I if ignorecase else 0
    regex = re.compile(find, flags)
    return regex.sub(replace, value)


def regex_search(value, find="", ignorecase=False):
    """Search using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.I if ignorecase else 0
    return bool(re.search(find, value, flags))


def regex_findall_index(value, find="", index=0, ignorecase=False):
    """Find all matches using regex and then pick specific match index."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.I if ignorecase else 0
    return re.findall(find, value, flags)[index]


def bitwise_and(first_value, second_value):
    """Perform a bitwise and operation."""
    return first_value & second_value


def bitwise_or(first_value, second_value):
    """Perform a bitwise or operation."""
    return first_value | second_value


def base64_encode(value):
    """Perform base64 encode."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def base64_decode(value):
    """Perform base64 denode."""
    return base64.b64decode(value).decode("utf-8")


def ordinal(value):
    """Perform ordinal conversion."""
    return str(value) + (
        list(["th", "st", "nd", "rd"] + ["th"] * 6)[(int(str(value)[-1])) % 10]
        if int(str(value)[-2:]) % 100 not in range(11, 14)
        else "th"
    )


def from_json(value):
    """Convert a JSON string to an object."""
    return json.loads(value)


def to_json(value):
    """Convert an object to a JSON string."""
    return json.dumps(value)


@contextfilter
def random_every_time(context, values):
    """Choose a random value.

    Unlike Jinja's random filter,
    this is context-dependent to avoid caching the chosen value.
    """
    return random.choice(values)


def relative_time(value):
    """
    Take a datetime and return its "age" as a string.

    The age can be in second, minute, hour, day, month or year. Only the
    biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
    be returned.
    Make sure date is not in the future, or else it will return None.

    If the input are not a datetime object the input will be returned unmodified.
    """

    if not isinstance(value, datetime):
        return value
    if not value.tzinfo:
        value = dt_util.as_local(value)
    if dt_util.now() < value:
        return value
    return dt_util.get_age(value)


class TemplateEnvironment(ImmutableSandboxedEnvironment):
    """The Home Assistant template environment."""

    def __init__(self, hass):
        """Initialise template environment."""
        super().__init__()
        self.hass = hass
        self.filters["round"] = forgiving_round
        self.filters["multiply"] = multiply
        self.filters["log"] = logarithm
        self.filters["sin"] = sine
        self.filters["cos"] = cosine
        self.filters["tan"] = tangent
        self.filters["asin"] = arc_sine
        self.filters["acos"] = arc_cosine
        self.filters["atan"] = arc_tangent
        self.filters["atan2"] = arc_tangent2
        self.filters["sqrt"] = square_root
        self.filters["as_timestamp"] = forgiving_as_timestamp
        self.filters["timestamp_custom"] = timestamp_custom
        self.filters["timestamp_local"] = timestamp_local
        self.filters["timestamp_utc"] = timestamp_utc
        self.filters["to_json"] = to_json
        self.filters["from_json"] = from_json
        self.filters["is_defined"] = fail_when_undefined
        self.filters["max"] = max
        self.filters["min"] = min
        self.filters["random"] = random_every_time
        self.filters["base64_encode"] = base64_encode
        self.filters["base64_decode"] = base64_decode
        self.filters["ordinal"] = ordinal
        self.filters["regex_match"] = regex_match
        self.filters["regex_replace"] = regex_replace
        self.filters["regex_search"] = regex_search
        self.filters["regex_findall_index"] = regex_findall_index
        self.filters["bitwise_and"] = bitwise_and
        self.filters["bitwise_or"] = bitwise_or
        self.filters["ord"] = ord
        self.globals["log"] = logarithm
        self.globals["sin"] = sine
        self.globals["cos"] = cosine
        self.globals["tan"] = tangent
        self.globals["sqrt"] = square_root
        self.globals["pi"] = math.pi
        self.globals["tau"] = math.pi * 2
        self.globals["e"] = math.e
        self.globals["asin"] = arc_sine
        self.globals["acos"] = arc_cosine
        self.globals["atan"] = arc_tangent
        self.globals["atan2"] = arc_tangent2
        self.globals["float"] = forgiving_float
        self.globals["now"] = dt_util.now
        self.globals["utcnow"] = dt_util.utcnow
        self.globals["as_timestamp"] = forgiving_as_timestamp
        self.globals["relative_time"] = relative_time
        self.globals["strptime"] = strptime
        if hass is None:
            return

        # We mark these as a context functions to ensure they get
        # evaluated fresh with every execution, rather than executed
        # at compile time and the value stored. The context itself
        # can be discarded, we only need to get at the hass object.
        def hassfunction(func):
            """Wrap function that depend on hass."""

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(hass, *args[1:], **kwargs)

            return contextfunction(wrapper)

        self.globals["expand"] = hassfunction(expand)
        self.filters["expand"] = contextfilter(self.globals["expand"])
        self.globals["closest"] = hassfunction(closest)
        self.filters["closest"] = contextfilter(hassfunction(closest_filter))
        self.globals["distance"] = hassfunction(distance)
        self.globals["is_state"] = hassfunction(is_state)
        self.globals["is_state_attr"] = hassfunction(is_state_attr)
        self.globals["state_attr"] = hassfunction(state_attr)
        self.globals["states"] = AllStates(hass)

    def is_safe_callable(self, obj):
        """Test if callback is safe."""
        return isinstance(obj, AllStates) or super().is_safe_callable(obj)

    def is_safe_attribute(self, obj, attr, value):
        """Test if attribute is safe."""
        return isinstance(obj, Namespace) or super().is_safe_attribute(obj, attr, value)


_NO_HASS_ENV = TemplateEnvironment(None)
