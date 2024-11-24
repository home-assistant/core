"""Template helper methods for rendering strings with Home Assistant data."""

from __future__ import annotations

from ast import literal_eval
import asyncio
import base64
import collections.abc
from collections.abc import Callable, Generator, Iterable
from contextlib import AbstractContextManager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from functools import cache, lru_cache, partial, wraps
import json
import logging
import math
from operator import contains
import pathlib
import random
import re
import statistics
from struct import error as StructError, pack, unpack_from
import sys
from types import CodeType, TracebackType
from typing import Any, Concatenate, Literal, NoReturn, Self, cast, overload
from urllib.parse import urlencode as urllib_urlencode
import weakref

from awesomeversion import AwesomeVersion
import jinja2
from jinja2 import pass_context, pass_environment, pass_eval_context
from jinja2.runtime import AsyncLoopContext, LoopContext
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2.utils import Namespace
from lru import LRU
import orjson
from propcache import under_cached_property
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_PERSONS,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
)
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceResponse,
    State,
    callback,
    split_entity_id,
    valid_domain,
    valid_entity_id,
)
from homeassistant.exceptions import TemplateError
from homeassistant.loader import bind_hass
from homeassistant.util import (
    convert,
    dt as dt_util,
    location as loc_util,
    slugify as slugify_util,
)
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads
from homeassistant.util.read_only_dict import ReadOnlyDict
from homeassistant.util.thread import ThreadWithException

from . import (
    area_registry,
    device_registry,
    entity_registry,
    floor_registry as fr,
    issue_registry,
    label_registry,
    location as loc_helper,
)
from .deprecation import deprecated_function
from .singleton import singleton
from .translation import async_translate_state
from .typing import TemplateVarsType

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)
_SENTINEL = object()
DATE_STR_FORMAT = "%Y-%m-%d %H:%M:%S"

_ENVIRONMENT: HassKey[TemplateEnvironment] = HassKey("template.environment")
_ENVIRONMENT_LIMITED: HassKey[TemplateEnvironment] = HassKey(
    "template.environment_limited"
)
_ENVIRONMENT_STRICT: HassKey[TemplateEnvironment] = HassKey(
    "template.environment_strict"
)
_HASS_LOADER = "template.hass_loader"

# Match "simple" ints and floats. -1.0, 1, +5, 5.0
_IS_NUMERIC = re.compile(r"^[+-]?(?!0\d)\d*(?:\.\d*)?$")

_RESERVED_NAMES = {
    "contextfunction",
    "evalcontextfunction",
    "environmentfunction",
    "jinja_pass_arg",
}

_COLLECTABLE_STATE_ATTRIBUTES = {
    "state",
    "attributes",
    "last_changed",
    "last_updated",
    "context",
    "domain",
    "object_id",
    "name",
}

ALL_STATES_RATE_LIMIT = 60  # seconds
DOMAIN_STATES_RATE_LIMIT = 1  # seconds

_render_info: ContextVar[RenderInfo | None] = ContextVar("_render_info", default=None)


template_cv: ContextVar[tuple[str, str] | None] = ContextVar(
    "template_cv", default=None
)

#
# CACHED_TEMPLATE_STATES is a rough estimate of the number of entities
# on a typical system. It is used as the initial size of the LRU cache
# for TemplateState objects.
#
# If the cache is too small we will end up creating and destroying
# TemplateState objects too often which will cause a lot of GC activity
# and slow down the system. For systems with a lot of entities and
# templates, this can reach 100000s of object creations and destructions
# per minute.
#
# Since entity counts may grow over time, we will increase
# the size if the number of entities grows via _async_adjust_lru_sizes
# at the start of the system and every 10 minutes if needed.
#
CACHED_TEMPLATE_STATES = 512
EVAL_CACHE_SIZE = 512

MAX_CUSTOM_TEMPLATE_SIZE = 5 * 1024 * 1024
MAX_TEMPLATE_OUTPUT = 256 * 1024  # 256KiB

CACHED_TEMPLATE_LRU: LRU[State, TemplateState] = LRU(CACHED_TEMPLATE_STATES)
CACHED_TEMPLATE_NO_COLLECT_LRU: LRU[State, TemplateState] = LRU(CACHED_TEMPLATE_STATES)
ENTITY_COUNT_GROWTH_FACTOR = 1.2

ORJSON_PASSTHROUGH_OPTIONS = (
    orjson.OPT_PASSTHROUGH_DATACLASS | orjson.OPT_PASSTHROUGH_DATETIME
)


def _template_state_no_collect(hass: HomeAssistant, state: State) -> TemplateState:
    """Return a TemplateState for a state without collecting."""
    if template_state := CACHED_TEMPLATE_NO_COLLECT_LRU.get(state):
        return template_state
    template_state = _create_template_state_no_collect(hass, state)
    CACHED_TEMPLATE_NO_COLLECT_LRU[state] = template_state
    return template_state


def _template_state(hass: HomeAssistant, state: State) -> TemplateState:
    """Return a TemplateState for a state that collects."""
    if template_state := CACHED_TEMPLATE_LRU.get(state):
        return template_state
    template_state = TemplateState(hass, state)
    CACHED_TEMPLATE_LRU[state] = template_state
    return template_state


def async_setup(hass: HomeAssistant) -> bool:
    """Set up tracking the template LRUs."""

    @callback
    def _async_adjust_lru_sizes(_: Any) -> None:
        """Adjust the lru cache sizes."""
        new_size = int(
            round(hass.states.async_entity_ids_count() * ENTITY_COUNT_GROWTH_FACTOR)
        )
        for lru in (CACHED_TEMPLATE_LRU, CACHED_TEMPLATE_NO_COLLECT_LRU):
            # There is no typing for LRU
            current_size = lru.get_size()
            if new_size > current_size:
                lru.set_size(new_size)

    from .event import (  # pylint: disable=import-outside-toplevel
        async_track_time_interval,
    )

    cancel = async_track_time_interval(
        hass, _async_adjust_lru_sizes, timedelta(minutes=10)
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_adjust_lru_sizes)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, callback(lambda _: cancel()))
    return True


@bind_hass
@deprecated_function(
    "automatic setting of Template.hass introduced by HA Core PR #89242",
    breaks_in_ha_version="2025.10",
)
def attach(hass: HomeAssistant, obj: Any) -> None:
    """Recursively attach hass to all template instances in list and dict."""
    return _attach(hass, obj)


def _attach(hass: HomeAssistant, obj: Any) -> None:
    """Recursively attach hass to all template instances in list and dict."""
    if isinstance(obj, list):
        for child in obj:
            _attach(hass, child)
    elif isinstance(obj, collections.abc.Mapping):
        for child_key, child_value in obj.items():
            _attach(hass, child_key)
            _attach(hass, child_value)
    elif isinstance(obj, Template):
        obj.hass = hass


def render_complex(
    value: Any,
    variables: TemplateVarsType = None,
    limited: bool = False,
    parse_result: bool = True,
) -> Any:
    """Recursive template creator helper function."""
    if isinstance(value, list):
        return [
            render_complex(item, variables, limited, parse_result) for item in value
        ]
    if isinstance(value, collections.abc.Mapping):
        return {
            render_complex(key, variables, limited, parse_result): render_complex(
                item, variables, limited, parse_result
            )
            for key, item in value.items()
        }
    if isinstance(value, Template):
        return value.async_render(variables, limited=limited, parse_result=parse_result)

    return value


def is_complex(value: Any) -> bool:
    """Test if data structure is a complex template."""
    if isinstance(value, Template):
        return True
    if isinstance(value, list):
        return any(is_complex(val) for val in value)
    if isinstance(value, collections.abc.Mapping):
        return any(is_complex(val) for val in value) or any(
            is_complex(val) for val in value.values()
        )
    return False


def is_template_string(maybe_template: str) -> bool:
    """Check if the input is a Jinja2 template."""
    return "{" in maybe_template and (
        "{%" in maybe_template or "{{" in maybe_template or "{#" in maybe_template
    )


class ResultWrapper:
    """Result wrapper class to store render result."""

    render_result: str | None


def gen_result_wrapper(kls: type[dict | list | set]) -> type:
    """Generate a result wrapper."""

    class Wrapper(kls, ResultWrapper):  # type: ignore[valid-type,misc]
        """Wrapper of a kls that can store render_result."""

        def __init__(self, *args: Any, render_result: str | None = None) -> None:
            super().__init__(*args)
            self.render_result = render_result

        def __str__(self) -> str:
            if self.render_result is None:
                # Can't get set repr to work
                if kls is set:
                    return str(set(self))

                return kls.__str__(self)

            return self.render_result

    return Wrapper


class TupleWrapper(tuple, ResultWrapper):
    """Wrap a tuple."""

    __slots__ = ()

    # This is all magic to be allowed to subclass a tuple.

    def __new__(cls, value: tuple, *, render_result: str | None = None) -> Self:
        """Create a new tuple class."""
        return super().__new__(cls, tuple(value))

    def __init__(self, value: tuple, *, render_result: str | None = None) -> None:
        """Initialize a new tuple class."""
        self.render_result = render_result

    def __str__(self) -> str:
        """Return string representation."""
        if self.render_result is None:
            return super().__str__()

        return self.render_result


_types: tuple[type[dict | list | set], ...] = (dict, list, set)
RESULT_WRAPPERS: dict[type, type] = {kls: gen_result_wrapper(kls) for kls in _types}
RESULT_WRAPPERS[tuple] = TupleWrapper


def _true(arg: str) -> bool:
    return True


def _false(arg: str) -> bool:
    return False


@lru_cache(maxsize=EVAL_CACHE_SIZE)
def _cached_parse_result(render_result: str) -> Any:
    """Parse a result and cache the result."""
    result = literal_eval(render_result)
    if type(result) in RESULT_WRAPPERS:
        result = RESULT_WRAPPERS[type(result)](result, render_result=render_result)

    # If the literal_eval result is a string, use the original
    # render, by not returning right here. The evaluation of strings
    # resulting in strings impacts quotes, to avoid unexpected
    # output; use the original render instead of the evaluated one.
    # Complex and scientific values are also unexpected. Filter them out.
    if (
        # Filter out string and complex numbers
        not isinstance(result, (str, complex))
        and (
            # Pass if not numeric and not a boolean
            not isinstance(result, (int, float))
            # Or it's a boolean (inherit from int)
            or isinstance(result, bool)
            # Or if it's a digit
            or _IS_NUMERIC.match(render_result) is not None
        )
    ):
        return result

    return render_result


class RenderInfo:
    """Holds information about a template render."""

    __slots__ = (
        "template",
        "filter_lifecycle",
        "filter",
        "_result",
        "is_static",
        "exception",
        "all_states",
        "all_states_lifecycle",
        "domains",
        "domains_lifecycle",
        "entities",
        "rate_limit",
        "has_time",
    )

    def __init__(self, template: Template) -> None:
        """Initialise."""
        self.template = template
        # Will be set sensibly once frozen.
        self.filter_lifecycle: Callable[[str], bool] = _true
        self.filter: Callable[[str], bool] = _true
        self._result: str | None = None
        self.is_static = False
        self.exception: TemplateError | None = None
        self.all_states = False
        self.all_states_lifecycle = False
        self.domains: collections.abc.Set[str] = set()
        self.domains_lifecycle: collections.abc.Set[str] = set()
        self.entities: collections.abc.Set[str] = set()
        self.rate_limit: float | None = None
        self.has_time = False

    def __repr__(self) -> str:
        """Representation of RenderInfo."""
        return (
            f"<RenderInfo {self.template}"
            f" all_states={self.all_states}"
            f" all_states_lifecycle={self.all_states_lifecycle}"
            f" domains={self.domains}"
            f" domains_lifecycle={self.domains_lifecycle}"
            f" entities={self.entities}"
            f" rate_limit={self.rate_limit}"
            f" has_time={self.has_time}"
            f" exception={self.exception}"
            f" is_static={self.is_static}"
            ">"
        )

    def _filter_domains_and_entities(self, entity_id: str) -> bool:
        """Template should re-render if the entity state changes.

        Only when we match specific domains or entities.
        """
        return (
            split_entity_id(entity_id)[0] in self.domains or entity_id in self.entities
        )

    def _filter_entities(self, entity_id: str) -> bool:
        """Template should re-render if the entity state changes.

        Only when we match specific entities.
        """
        return entity_id in self.entities

    def _filter_lifecycle_domains(self, entity_id: str) -> bool:
        """Template should re-render if the entity is added or removed.

        Only with domains watched.
        """
        return split_entity_id(entity_id)[0] in self.domains_lifecycle

    def result(self) -> str:
        """Results of the template computation."""
        if self.exception is not None:
            raise self.exception
        return cast(str, self._result)

    def _freeze_static(self) -> None:
        self.is_static = True
        self._freeze_sets()
        self.all_states = False

    def _freeze_sets(self) -> None:
        self.entities = frozenset(self.entities)
        self.domains = frozenset(self.domains)
        self.domains_lifecycle = frozenset(self.domains_lifecycle)

    def _freeze(self) -> None:
        self._freeze_sets()

        if self.rate_limit is None:
            if self.all_states or self.exception:
                self.rate_limit = ALL_STATES_RATE_LIMIT
            elif self.domains or self.domains_lifecycle:
                self.rate_limit = DOMAIN_STATES_RATE_LIMIT

        if self.exception:
            return

        if not self.all_states_lifecycle:
            if self.domains_lifecycle:
                self.filter_lifecycle = self._filter_lifecycle_domains
            else:
                self.filter_lifecycle = _false

        if self.all_states:
            return

        if self.domains:
            self.filter = self._filter_domains_and_entities
        elif self.entities:
            self.filter = self._filter_entities
        else:
            self.filter = _false


class Template:
    """Class to hold a template and manage caching and rendering."""

    __slots__ = (
        "__weakref__",
        "template",
        "hass",
        "is_static",
        "_compiled_code",
        "_compiled",
        "_exc_info",
        "_limited",
        "_strict",
        "_log_fn",
        "_hash_cache",
        "_renders",
    )

    def __init__(self, template: str, hass: HomeAssistant | None = None) -> None:
        """Instantiate a template.

        Note: A valid hass instance should always be passed in. The hass parameter
        will be non optional in Home Assistant Core 2025.10.
        """
        # pylint: disable-next=import-outside-toplevel
        from .frame import ReportBehavior, report_usage

        if not isinstance(template, str):
            raise TypeError("Expected template to be a string")

        if not hass:
            report_usage(
                "creates a template object without passing hass",
                core_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2025.10",
            )

        self.template: str = template.strip()
        self._compiled_code: CodeType | None = None
        self._compiled: jinja2.Template | None = None
        self.hass = hass
        self.is_static = not is_template_string(template)
        self._exc_info: sys._OptExcInfo | None = None
        self._limited: bool | None = None
        self._strict: bool | None = None
        self._log_fn: Callable[[int, str], None] | None = None
        self._hash_cache: int = hash(self.template)
        self._renders: int = 0

    @property
    def _env(self) -> TemplateEnvironment:
        if self.hass is None:
            return _NO_HASS_ENV
        # Bypass cache if a custom log function is specified
        if self._log_fn is not None:
            return TemplateEnvironment(
                self.hass, self._limited, self._strict, self._log_fn
            )
        if self._limited:
            wanted_env = _ENVIRONMENT_LIMITED
        elif self._strict:
            wanted_env = _ENVIRONMENT_STRICT
        else:
            wanted_env = _ENVIRONMENT
        if (ret := self.hass.data.get(wanted_env)) is None:
            ret = self.hass.data[wanted_env] = TemplateEnvironment(
                self.hass, self._limited, self._strict, self._log_fn
            )
        return ret

    def ensure_valid(self) -> None:
        """Return if template is valid."""
        if self.is_static or self._compiled_code is not None:
            return

        if compiled := self._env.template_cache.get(self.template):
            self._compiled_code = compiled
            return

        with _template_context_manager as cm:
            cm.set_template(self.template, "compiling")
            try:
                self._compiled_code = self._env.compile(self.template)
            except jinja2.TemplateError as err:
                raise TemplateError(err) from err

    def render(
        self,
        variables: TemplateVarsType = None,
        parse_result: bool = True,
        limited: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Render given template.

        If limited is True, the template is not allowed to access any function
        or filter depending on hass or the state machine.
        """
        if self.is_static:
            if not parse_result or self.hass and self.hass.config.legacy_templates:
                return self.template
            return self._parse_result(self.template)
        assert self.hass is not None, "hass variable not set on template"
        return run_callback_threadsafe(
            self.hass.loop,
            partial(self.async_render, variables, parse_result, limited, **kwargs),
        ).result()

    @callback
    def async_render(
        self,
        variables: TemplateVarsType = None,
        parse_result: bool = True,
        limited: bool = False,
        strict: bool = False,
        log_fn: Callable[[int, str], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Render given template.

        This method must be run in the event loop.

        If limited is True, the template is not allowed to access any function
        or filter depending on hass or the state machine.
        """
        self._renders += 1

        if self.is_static:
            if not parse_result or self.hass and self.hass.config.legacy_templates:
                return self.template
            return self._parse_result(self.template)

        compiled = self._compiled or self._ensure_compiled(limited, strict, log_fn)

        if variables is not None:
            kwargs.update(variables)

        try:
            render_result = _render_with_context(self.template, compiled, **kwargs)
        except Exception as err:
            raise TemplateError(err) from err

        if len(render_result) > MAX_TEMPLATE_OUTPUT:
            raise TemplateError(
                f"Template output exceeded maximum size of {MAX_TEMPLATE_OUTPUT} characters"
            )

        render_result = render_result.strip()

        if not parse_result or self.hass and self.hass.config.legacy_templates:
            return render_result

        return self._parse_result(render_result)

    def _parse_result(self, render_result: str) -> Any:
        """Parse the result."""
        try:
            return _cached_parse_result(render_result)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            pass

        return render_result

    async def async_render_will_timeout(
        self,
        timeout: float,
        variables: TemplateVarsType = None,
        strict: bool = False,
        log_fn: Callable[[int, str], None] | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check to see if rendering a template will timeout during render.

        This is intended to check for expensive templates
        that will make the system unstable.  The template
        is rendered in the executor to ensure it does not
        tie up the event loop.

        This function is not a security control and is only
        intended to be used as a safety check when testing
        templates.

        This method must be run in the event loop.
        """
        self._renders += 1

        if self.is_static:
            return False

        compiled = self._compiled or self._ensure_compiled(strict=strict, log_fn=log_fn)

        if variables is not None:
            kwargs.update(variables)

        self._exc_info = None
        finish_event = asyncio.Event()

        def _render_template() -> None:
            assert self.hass is not None, "hass variable not set on template"
            try:
                _render_with_context(self.template, compiled, **kwargs)
            except TimeoutError:
                pass
            except Exception:  # noqa: BLE001
                self._exc_info = sys.exc_info()
            finally:
                self.hass.loop.call_soon_threadsafe(finish_event.set)

        try:
            template_render_thread = ThreadWithException(target=_render_template)
            template_render_thread.start()
            async with asyncio.timeout(timeout):
                await finish_event.wait()
            if self._exc_info:
                raise TemplateError(self._exc_info[1].with_traceback(self._exc_info[2]))
        except TimeoutError:
            template_render_thread.raise_exc(TimeoutError)
            return True
        finally:
            template_render_thread.join()

        return False

    @callback
    def async_render_to_info(
        self,
        variables: TemplateVarsType = None,
        strict: bool = False,
        log_fn: Callable[[int, str], None] | None = None,
        **kwargs: Any,
    ) -> RenderInfo:
        """Render the template and collect an entity filter."""
        if self.hass and self.hass.config.debug:
            self.hass.verify_event_loop_thread("async_render_to_info")
        self._renders += 1

        render_info = RenderInfo(self)

        if not self.hass:
            raise RuntimeError(f"hass not set while rendering {self}")

        if _render_info.get() is not None:
            raise RuntimeError(
                f"RenderInfo already set while rendering {self}, "
                "this usually indicates the template is being rendered "
                "in the wrong thread"
            )

        if self.is_static:
            render_info._result = self.template.strip()  # noqa: SLF001
            render_info._freeze_static()  # noqa: SLF001
            return render_info

        token = _render_info.set(render_info)
        try:
            render_info._result = self.async_render(  # noqa: SLF001
                variables, strict=strict, log_fn=log_fn, **kwargs
            )
        except TemplateError as ex:
            render_info.exception = ex
        finally:
            _render_info.reset(token)

        render_info._freeze()  # noqa: SLF001
        return render_info

    def render_with_possible_json_value(self, value, error_value=_SENTINEL):
        """Render template with value exposed.

        If valid JSON will expose value_json too.
        """
        if self.is_static:
            return self.template

        return run_callback_threadsafe(
            self.hass.loop,
            self.async_render_with_possible_json_value,
            value,
            error_value,
        ).result()

    @callback
    def async_render_with_possible_json_value(
        self,
        value: Any,
        error_value: Any = _SENTINEL,
        variables: dict[str, Any] | None = None,
        parse_result: bool = False,
    ) -> Any:
        """Render template with value exposed.

        If valid JSON will expose value_json too.

        This method must be run in the event loop.
        """
        self._renders += 1

        if self.is_static:
            return self.template

        compiled = self._compiled or self._ensure_compiled()

        variables = dict(variables or {})
        variables["value"] = value

        try:  # noqa: SIM105 - suppress is much slower
            variables["value_json"] = json_loads(value)
        except JSON_DECODE_EXCEPTIONS:
            pass

        try:
            render_result = _render_with_context(
                self.template, compiled, **variables
            ).strip()
        except jinja2.TemplateError as ex:
            if error_value is _SENTINEL:
                _LOGGER.error(
                    "Error parsing value: %s (value: %s, template: %s)",
                    ex,
                    value,
                    self.template,
                )
            return value if error_value is _SENTINEL else error_value

        if not parse_result or self.hass and self.hass.config.legacy_templates:
            return render_result

        return self._parse_result(render_result)

    def _ensure_compiled(
        self,
        limited: bool = False,
        strict: bool = False,
        log_fn: Callable[[int, str], None] | None = None,
    ) -> jinja2.Template:
        """Bind a template to a specific hass instance."""
        self.ensure_valid()

        assert self.hass is not None, "hass variable not set on template"
        assert (
            self._limited is None or self._limited == limited
        ), "can't change between limited and non limited template"
        assert (
            self._strict is None or self._strict == strict
        ), "can't change between strict and non strict template"
        assert not (strict and limited), "can't combine strict and limited template"
        assert (
            self._log_fn is None or self._log_fn == log_fn
        ), "can't change custom log function"
        assert self._compiled_code is not None, "template code was not compiled"

        self._limited = limited
        self._strict = strict
        self._log_fn = log_fn
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
        return self._hash_cache

    def __repr__(self) -> str:
        """Representation of Template."""
        return f"Template<template=({self.template}) renders={self._renders}>"


@cache
def _domain_states(hass: HomeAssistant, name: str) -> DomainStates:
    return DomainStates(hass, name)


def _readonly(*args: Any, **kwargs: Any) -> Any:
    """Raise an exception when a states object is modified."""
    raise RuntimeError(f"Cannot modify template States object: {args} {kwargs}")


class AllStates:
    """Class to expose all HA states as attributes."""

    __setitem__ = _readonly
    __delitem__ = _readonly
    __slots__ = ("_hass",)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize all states."""
        self._hass = hass

    def __getattr__(self, name):
        """Return the domain state."""
        if "." in name:
            return _get_state_if_valid(self._hass, name)

        if name in _RESERVED_NAMES:
            return None

        if not valid_domain(name):
            raise TemplateError(f"Invalid domain name '{name}'")

        return _domain_states(self._hass, name)

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    __getitem__ = __getattr__

    def _collect_all(self) -> None:
        if (render_info := _render_info.get()) is not None:
            render_info.all_states = True

    def _collect_all_lifecycle(self) -> None:
        if (render_info := _render_info.get()) is not None:
            render_info.all_states_lifecycle = True

    def __iter__(self) -> Generator[TemplateState]:
        """Return all states."""
        self._collect_all()
        return _state_generator(self._hass, None)

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_all_lifecycle()
        return self._hass.states.async_entity_ids_count()

    def __call__(
        self,
        entity_id: str,
        rounded: bool | object = _SENTINEL,
        with_unit: bool = False,
    ) -> str:
        """Return the states."""
        state = _get_state(self._hass, entity_id)
        if state is None:
            return STATE_UNKNOWN
        if rounded is _SENTINEL:
            rounded = with_unit
        if rounded or with_unit:
            return state.format_state(rounded, with_unit)  # type: ignore[arg-type]
        return state.state

    def __repr__(self) -> str:
        """Representation of All States."""
        return "<template AllStates>"


class StateTranslated:
    """Class to represent a translated state in a template."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize all states."""
        self._hass = hass

    def __call__(self, entity_id: str) -> str | None:
        """Retrieve translated state if available."""
        state = _get_state_if_valid(self._hass, entity_id)

        if state is None:
            return STATE_UNKNOWN

        state_value = state.state
        domain = state.domain
        device_class = state.attributes.get("device_class")
        entry = entity_registry.async_get(self._hass).async_get(entity_id)
        platform = None if entry is None else entry.platform
        translation_key = None if entry is None else entry.translation_key

        return async_translate_state(
            self._hass, state_value, domain, platform, translation_key, device_class
        )

    def __repr__(self) -> str:
        """Representation of Translated state."""
        return "<template StateTranslated>"


class DomainStates:
    """Class to expose a specific HA domain as attributes."""

    __slots__ = ("_hass", "_domain")

    __setitem__ = _readonly
    __delitem__ = _readonly

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the domain states."""
        self._hass = hass
        self._domain = domain

    def __getattr__(self, name: str) -> TemplateState | None:
        """Return the states."""
        return _get_state_if_valid(self._hass, f"{self._domain}.{name}")

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    __getitem__ = __getattr__

    def _collect_domain(self) -> None:
        if (entity_collect := _render_info.get()) is not None:
            entity_collect.domains.add(self._domain)  # type: ignore[attr-defined]

    def _collect_domain_lifecycle(self) -> None:
        if (entity_collect := _render_info.get()) is not None:
            entity_collect.domains_lifecycle.add(self._domain)  # type: ignore[attr-defined]

    def __iter__(self) -> Generator[TemplateState]:
        """Return the iteration over all the states."""
        self._collect_domain()
        return _state_generator(self._hass, self._domain)

    def __len__(self) -> int:
        """Return number of states."""
        self._collect_domain_lifecycle()
        return self._hass.states.async_entity_ids_count(self._domain)

    def __repr__(self) -> str:
        """Representation of Domain States."""
        return f"<template DomainStates('{self._domain}')>"


class TemplateStateBase(State):
    """Class to represent a state object in a template."""

    __slots__ = ("_hass", "_collect", "_entity_id", "_state")

    _state: State

    __setitem__ = _readonly
    __delitem__ = _readonly

    # Inheritance is done so functions that check against State keep working
    # pylint: disable-next=super-init-not-called
    def __init__(self, hass: HomeAssistant, collect: bool, entity_id: str) -> None:
        """Initialize template state."""
        self._hass = hass
        self._collect = collect
        self._entity_id = entity_id
        self._cache: dict[str, Any] = {}

    def _collect_state(self) -> None:
        if self._collect and (render_info := _render_info.get()):
            render_info.entities.add(self._entity_id)  # type: ignore[attr-defined]

    # Jinja will try __getitem__ first and it avoids the need
    # to call is_safe_attribute
    def __getitem__(self, item: str) -> Any:
        """Return a property as an attribute for jinja."""
        if item in _COLLECTABLE_STATE_ATTRIBUTES:
            # _collect_state inlined here for performance
            if self._collect and (render_info := _render_info.get()):
                render_info.entities.add(self._entity_id)  # type: ignore[attr-defined]
            return getattr(self._state, item)
        if item == "entity_id":
            return self._entity_id
        if item == "state_with_unit":
            return self.state_with_unit
        raise KeyError

    @under_cached_property
    def entity_id(self) -> str:  # type: ignore[override]
        """Wrap State.entity_id.

        Intentionally does not collect state
        """
        return self._entity_id

    @property
    def state(self) -> str:  # type: ignore[override]
        """Wrap State.state."""
        self._collect_state()
        return self._state.state

    @property
    def attributes(self) -> ReadOnlyDict[str, Any]:  # type: ignore[override]
        """Wrap State.attributes."""
        self._collect_state()
        return self._state.attributes

    @property
    def last_changed(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_changed."""
        self._collect_state()
        return self._state.last_changed

    @property
    def last_reported(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_reported."""
        self._collect_state()
        return self._state.last_reported

    @property
    def last_updated(self) -> datetime:  # type: ignore[override]
        """Wrap State.last_updated."""
        self._collect_state()
        return self._state.last_updated

    @property
    def context(self) -> Context:  # type: ignore[override]
        """Wrap State.context."""
        self._collect_state()
        return self._state.context

    @property
    def domain(self) -> str:  # type: ignore[override]
        """Wrap State.domain."""
        self._collect_state()
        return self._state.domain

    @property
    def object_id(self) -> str:  # type: ignore[override]
        """Wrap State.object_id."""
        self._collect_state()
        return self._state.object_id

    @property
    def name(self) -> str:  # type: ignore[override]
        """Wrap State.name."""
        self._collect_state()
        return self._state.name

    @property
    def state_with_unit(self) -> str:
        """Return the state concatenated with the unit if available."""
        return self.format_state(rounded=True, with_unit=True)

    def format_state(self, rounded: bool, with_unit: bool) -> str:
        """Return a formatted version of the state."""
        # Import here, not at top-level, to avoid circular import
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.sensor import (
            DOMAIN as SENSOR_DOMAIN,
            async_rounded_state,
        )

        self._collect_state()
        if rounded and self._state.domain == SENSOR_DOMAIN:
            state = async_rounded_state(self._hass, self._entity_id, self._state)
        else:
            state = self._state.state
        if with_unit and (unit := self._state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)):
            return f"{state} {unit}"
        return state

    def __eq__(self, other: object) -> bool:
        """Ensure we collect on equality check."""
        self._collect_state()
        return self._state.__eq__(other)


class TemplateState(TemplateStateBase):
    """Class to represent a state object in a template."""

    __slots__ = ()

    # Inheritance is done so functions that check against State keep working
    def __init__(self, hass: HomeAssistant, state: State, collect: bool = True) -> None:
        """Initialize template state."""
        super().__init__(hass, collect, state.entity_id)
        self._state = state

    def __repr__(self) -> str:
        """Representation of Template State."""
        return f"<template TemplateState({self._state!r})>"


class TemplateStateFromEntityId(TemplateStateBase):
    """Class to represent a state object in a template."""

    __slots__ = ()

    def __init__(
        self, hass: HomeAssistant, entity_id: str, collect: bool = True
    ) -> None:
        """Initialize template state."""
        super().__init__(hass, collect, entity_id)

    @property
    def _state(self) -> State:  # type: ignore[override]
        state = self._hass.states.get(self._entity_id)
        if not state:
            state = State(self._entity_id, STATE_UNKNOWN)
        return state

    def __repr__(self) -> str:
        """Representation of Template State."""
        return f"<template TemplateStateFromEntityId({self._entity_id})>"


_create_template_state_no_collect = partial(TemplateState, collect=False)


def _collect_state(hass: HomeAssistant, entity_id: str) -> None:
    if (entity_collect := _render_info.get()) is not None:
        entity_collect.entities.add(entity_id)  # type: ignore[attr-defined]


def _state_generator(
    hass: HomeAssistant, domain: str | None
) -> Generator[TemplateState]:
    """State generator for a domain or all states."""
    states = hass.states
    # If domain is None, we want to iterate over all states, but making
    # a copy of the dict is expensive. So we iterate over the protected
    # _states dict instead. This is safe because we're not modifying it
    # and everything is happening in the same thread (MainThread).
    #
    # We do not want to expose this method in the public API though to
    # ensure it does not get misused.
    #
    container: Iterable[State]
    if domain is None:
        container = states._states.values()  # noqa: SLF001
    else:
        container = states.async_all(domain)
    for state in container:
        yield _template_state_no_collect(hass, state)


def _get_state_if_valid(hass: HomeAssistant, entity_id: str) -> TemplateState | None:
    state = hass.states.get(entity_id)
    if state is None and not valid_entity_id(entity_id):
        raise TemplateError(f"Invalid entity ID '{entity_id}'")
    return _get_template_state_from_state(hass, entity_id, state)


def _get_state(hass: HomeAssistant, entity_id: str) -> TemplateState | None:
    return _get_template_state_from_state(hass, entity_id, hass.states.get(entity_id))


def _get_template_state_from_state(
    hass: HomeAssistant, entity_id: str, state: State | None
) -> TemplateState | None:
    if state is None:
        # Only need to collect if none, if not none collect first actual
        # access to the state properties in the state wrapper.
        _collect_state(hass, entity_id)
        return None
    return _template_state(hass, state)


def _resolve_state(
    hass: HomeAssistant, entity_id_or_state: Any
) -> State | TemplateState | None:
    """Return state or entity_id if given."""
    if isinstance(entity_id_or_state, State):
        return entity_id_or_state
    if isinstance(entity_id_or_state, str):
        return _get_state(hass, entity_id_or_state)
    return None


@overload
def forgiving_boolean(value: Any) -> bool | object: ...


@overload
def forgiving_boolean[_T](value: Any, default: _T) -> bool | _T: ...


def forgiving_boolean[_T](
    value: Any, default: _T | object = _SENTINEL
) -> bool | _T | object:
    """Try to convert value to a boolean."""
    try:
        # Import here, not at top-level to avoid circular import
        from . import config_validation as cv  # pylint: disable=import-outside-toplevel

        return cv.boolean(value)
    except vol.Invalid:
        if default is _SENTINEL:
            raise_no_default("bool", value)
        return default


def result_as_boolean(template_result: Any | None) -> bool:
    """Convert the template result to a boolean.

    True/not 0/'1'/'true'/'yes'/'on'/'enable' are considered truthy
    False/0/None/'0'/'false'/'no'/'off'/'disable' are considered falsy
    All other values are falsy
    """
    if template_result is None:
        return False

    return forgiving_boolean(template_result, default=False)


def expand(hass: HomeAssistant, *args: Any) -> Iterable[State]:
    """Expand out any groups and zones into entity states."""
    # circular import.
    from . import entity as entity_helper  # pylint: disable=import-outside-toplevel

    search = list(args)
    found = {}
    sources = entity_helper.entity_sources(hass)
    while search:
        entity = search.pop()
        if isinstance(entity, str):
            entity_id = entity
            if (entity := _get_state(hass, entity)) is None:
                continue
        elif isinstance(entity, State):
            entity_id = entity.entity_id
        elif isinstance(entity, collections.abc.Iterable):
            search += entity
            continue
        else:
            # ignore other types
            continue

        if entity_id in found:
            continue

        domain = entity.domain
        if domain == "group" or (
            (source := sources.get(entity_id)) and source["domain"] == "group"
        ):
            # Collect state will be called in here since it's wrapped
            if group_entities := entity.attributes.get(ATTR_ENTITY_ID):
                search += group_entities
        elif domain == "zone":
            if zone_entities := entity.attributes.get(ATTR_PERSONS):
                search += zone_entities
        else:
            _collect_state(hass, entity_id)
            found[entity_id] = entity

    return list(found.values())


def device_entities(hass: HomeAssistant, _device_id: str) -> Iterable[str]:
    """Get entity ids for entities tied to a device."""
    entity_reg = entity_registry.async_get(hass)
    entries = entity_registry.async_entries_for_device(entity_reg, _device_id)
    return [entry.entity_id for entry in entries]


def integration_entities(hass: HomeAssistant, entry_name: str) -> Iterable[str]:
    """Get entity ids for entities tied to an integration/domain.

    Provide entry_name as domain to get all entity id's for a integration/domain
    or provide a config entry title for filtering between instances of the same
    integration.
    """

    # Don't allow searching for config entries without title
    if not entry_name:
        return []

    # first try if there are any config entries with a matching title
    entities: list[str] = []
    ent_reg = entity_registry.async_get(hass)
    for entry in hass.config_entries.async_entries():
        if entry.title != entry_name:
            continue
        entries = entity_registry.async_entries_for_config_entry(
            ent_reg, entry.entry_id
        )
        entities.extend(entry.entity_id for entry in entries)
    if entities:
        return entities

    # fallback to just returning all entities for a domain
    # pylint: disable-next=import-outside-toplevel
    from .entity import entity_sources

    return [
        entity_id
        for entity_id, info in entity_sources(hass).items()
        if info["domain"] == entry_name
    ]


def config_entry_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Get an config entry ID from an entity ID."""
    entity_reg = entity_registry.async_get(hass)
    if entity := entity_reg.async_get(entity_id):
        return entity.config_entry_id
    return None


def device_id(hass: HomeAssistant, entity_id_or_device_name: str) -> str | None:
    """Get a device ID from an entity ID or device name."""
    entity_reg = entity_registry.async_get(hass)
    entity = entity_reg.async_get(entity_id_or_device_name)
    if entity is not None:
        return entity.device_id

    dev_reg = device_registry.async_get(hass)
    return next(
        (
            device_id
            for device_id, device in dev_reg.devices.items()
            if (name := device.name_by_user or device.name)
            and (str(entity_id_or_device_name) == name)
        ),
        None,
    )


def device_attr(hass: HomeAssistant, device_or_entity_id: str, attr_name: str) -> Any:
    """Get the device specific attribute."""
    device_reg = device_registry.async_get(hass)
    if not isinstance(device_or_entity_id, str):
        raise TemplateError("Must provide a device or entity ID")
    device = None
    if (
        "." in device_or_entity_id
        and (_device_id := device_id(hass, device_or_entity_id)) is not None
    ):
        device = device_reg.async_get(_device_id)
    elif "." not in device_or_entity_id:
        device = device_reg.async_get(device_or_entity_id)
    if device is None or not hasattr(device, attr_name):
        return None
    return getattr(device, attr_name)


def config_entry_attr(
    hass: HomeAssistant, config_entry_id_: str, attr_name: str
) -> Any:
    """Get config entry specific attribute."""
    if not isinstance(config_entry_id_, str):
        raise TemplateError("Must provide a config entry ID")

    if attr_name not in ("domain", "title", "state", "source", "disabled_by"):
        raise TemplateError("Invalid config entry attribute")

    config_entry = hass.config_entries.async_get_entry(config_entry_id_)

    if config_entry is None:
        return None

    return getattr(config_entry, attr_name)


def is_device_attr(
    hass: HomeAssistant, device_or_entity_id: str, attr_name: str, attr_value: Any
) -> bool:
    """Test if a device's attribute is a specific value."""
    return bool(device_attr(hass, device_or_entity_id, attr_name) == attr_value)


def issues(hass: HomeAssistant) -> dict[tuple[str, str], dict[str, Any]]:
    """Return all open issues."""
    current_issues = issue_registry.async_get(hass).issues
    # Use JSON for safe representation
    return {k: v.to_json() for (k, v) in current_issues.items()}


def issue(hass: HomeAssistant, domain: str, issue_id: str) -> dict[str, Any] | None:
    """Get issue by domain and issue_id."""
    result = issue_registry.async_get(hass).async_get_issue(domain, issue_id)
    if result:
        return result.to_json()
    return None


def floors(hass: HomeAssistant) -> Iterable[str | None]:
    """Return all floors."""
    floor_registry = fr.async_get(hass)
    return [floor.floor_id for floor in floor_registry.async_list_floors()]


def floor_id(hass: HomeAssistant, lookup_value: Any) -> str | None:
    """Get the floor ID from a floor name."""
    floor_registry = fr.async_get(hass)
    if floor := floor_registry.async_get_floor_by_name(str(lookup_value)):
        return floor.floor_id

    if aid := area_id(hass, lookup_value):
        area_reg = area_registry.async_get(hass)
        if area := area_reg.async_get_area(aid):
            return area.floor_id

    return None


def floor_name(hass: HomeAssistant, lookup_value: str) -> str | None:
    """Get the floor name from a floor id."""
    floor_registry = fr.async_get(hass)
    if floor := floor_registry.async_get_floor(lookup_value):
        return floor.name

    if aid := area_id(hass, lookup_value):
        area_reg = area_registry.async_get(hass)
        if (
            (area := area_reg.async_get_area(aid))
            and area.floor_id
            and (floor := floor_registry.async_get_floor(area.floor_id))
        ):
            return floor.name

    return None


def floor_areas(hass: HomeAssistant, floor_id_or_name: str) -> Iterable[str]:
    """Return area IDs for a given floor ID or name."""
    _floor_id: str | None
    # If floor_name returns a value, we know the input was an ID, otherwise we
    # assume it's a name, and if it's neither, we return early
    if floor_name(hass, floor_id_or_name) is not None:
        _floor_id = floor_id_or_name
    else:
        _floor_id = floor_id(hass, floor_id_or_name)
    if _floor_id is None:
        return []

    area_reg = area_registry.async_get(hass)
    entries = area_registry.async_entries_for_floor(area_reg, _floor_id)
    return [entry.id for entry in entries if entry.id]


def areas(hass: HomeAssistant) -> Iterable[str | None]:
    """Return all areas."""
    return list(area_registry.async_get(hass).areas)


def area_id(hass: HomeAssistant, lookup_value: str) -> str | None:
    """Get the area ID from an area name, device id, or entity id."""
    area_reg = area_registry.async_get(hass)
    if area := area_reg.async_get_area_by_name(str(lookup_value)):
        return area.id

    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)
    # Import here, not at top-level to avoid circular import
    from . import config_validation as cv  # pylint: disable=import-outside-toplevel

    try:
        cv.entity_id(lookup_value)
    except vol.Invalid:
        pass
    else:
        if entity := ent_reg.async_get(lookup_value):
            # If entity has an area ID, return that
            if entity.area_id:
                return entity.area_id
            # If entity has a device ID, return the area ID for the device
            if entity.device_id and (device := dev_reg.async_get(entity.device_id)):
                return device.area_id

    # Check if this could be a device ID
    if device := dev_reg.async_get(lookup_value):
        return device.area_id

    return None


def _get_area_name(area_reg: area_registry.AreaRegistry, valid_area_id: str) -> str:
    """Get area name from valid area ID."""
    area = area_reg.async_get_area(valid_area_id)
    assert area
    return area.name


def area_name(hass: HomeAssistant, lookup_value: str) -> str | None:
    """Get the area name from an area id, device id, or entity id."""
    area_reg = area_registry.async_get(hass)
    if area := area_reg.async_get_area(lookup_value):
        return area.name

    dev_reg = device_registry.async_get(hass)
    ent_reg = entity_registry.async_get(hass)
    # Import here, not at top-level to avoid circular import
    from . import config_validation as cv  # pylint: disable=import-outside-toplevel

    try:
        cv.entity_id(lookup_value)
    except vol.Invalid:
        pass
    else:
        if entity := ent_reg.async_get(lookup_value):
            # If entity has an area ID, get the area name for that
            if entity.area_id:
                return _get_area_name(area_reg, entity.area_id)
            # If entity has a device ID and the device exists with an area ID, get the
            # area name for that
            if (
                entity.device_id
                and (device := dev_reg.async_get(entity.device_id))
                and device.area_id
            ):
                return _get_area_name(area_reg, device.area_id)

    if (device := dev_reg.async_get(lookup_value)) and device.area_id:
        return _get_area_name(area_reg, device.area_id)

    return None


def area_entities(hass: HomeAssistant, area_id_or_name: str) -> Iterable[str]:
    """Return entities for a given area ID or name."""
    _area_id: str | None
    # if area_name returns a value, we know the input was an ID, otherwise we
    # assume it's a name, and if it's neither, we return early
    if area_name(hass, area_id_or_name) is None:
        _area_id = area_id(hass, area_id_or_name)
    else:
        _area_id = area_id_or_name
    if _area_id is None:
        return []
    ent_reg = entity_registry.async_get(hass)
    entity_ids = [
        entry.entity_id
        for entry in entity_registry.async_entries_for_area(ent_reg, _area_id)
    ]
    dev_reg = device_registry.async_get(hass)
    # We also need to add entities tied to a device in the area that don't themselves
    # have an area specified since they inherit the area from the device.
    entity_ids.extend(
        [
            entity.entity_id
            for device in device_registry.async_entries_for_area(dev_reg, _area_id)
            for entity in entity_registry.async_entries_for_device(ent_reg, device.id)
            if entity.area_id is None
        ]
    )
    return entity_ids


def area_devices(hass: HomeAssistant, area_id_or_name: str) -> Iterable[str]:
    """Return device IDs for a given area ID or name."""
    _area_id: str | None
    # if area_name returns a value, we know the input was an ID, otherwise we
    # assume it's a name, and if it's neither, we return early
    if area_name(hass, area_id_or_name) is not None:
        _area_id = area_id_or_name
    else:
        _area_id = area_id(hass, area_id_or_name)
    if _area_id is None:
        return []
    dev_reg = device_registry.async_get(hass)
    entries = device_registry.async_entries_for_area(dev_reg, _area_id)
    return [entry.id for entry in entries]


def labels(hass: HomeAssistant, lookup_value: Any = None) -> Iterable[str | None]:
    """Return all labels, or those from a area ID, device ID, or entity ID."""
    label_reg = label_registry.async_get(hass)
    if lookup_value is None:
        return list(label_reg.labels)

    ent_reg = entity_registry.async_get(hass)

    # Import here, not at top-level to avoid circular import
    from . import config_validation as cv  # pylint: disable=import-outside-toplevel

    lookup_value = str(lookup_value)

    try:
        cv.entity_id(lookup_value)
    except vol.Invalid:
        pass
    else:
        if entity := ent_reg.async_get(lookup_value):
            return list(entity.labels)

    # Check if this could be a device ID
    dev_reg = device_registry.async_get(hass)
    if device := dev_reg.async_get(lookup_value):
        return list(device.labels)

    # Check if this could be a area ID
    area_reg = area_registry.async_get(hass)
    if area := area_reg.async_get_area(lookup_value):
        return list(area.labels)

    return []


def label_id(hass: HomeAssistant, lookup_value: Any) -> str | None:
    """Get the label ID from a label name."""
    label_reg = label_registry.async_get(hass)
    if label := label_reg.async_get_label_by_name(str(lookup_value)):
        return label.label_id
    return None


def label_name(hass: HomeAssistant, lookup_value: str) -> str | None:
    """Get the label name from a label ID."""
    label_reg = label_registry.async_get(hass)
    if label := label_reg.async_get_label(lookup_value):
        return label.name
    return None


def _label_id_or_name(hass: HomeAssistant, label_id_or_name: str) -> str | None:
    """Get the label ID from a label name or ID."""
    # If label_name returns a value, we know the input was an ID, otherwise we
    # assume it's a name, and if it's neither, we return early.
    if label_name(hass, label_id_or_name) is not None:
        return label_id_or_name
    return label_id(hass, label_id_or_name)


def label_areas(hass: HomeAssistant, label_id_or_name: str) -> Iterable[str]:
    """Return areas for a given label ID or name."""
    if (_label_id := _label_id_or_name(hass, label_id_or_name)) is None:
        return []
    area_reg = area_registry.async_get(hass)
    entries = area_registry.async_entries_for_label(area_reg, _label_id)
    return [entry.id for entry in entries]


def label_devices(hass: HomeAssistant, label_id_or_name: str) -> Iterable[str]:
    """Return device IDs for a given label ID or name."""
    if (_label_id := _label_id_or_name(hass, label_id_or_name)) is None:
        return []
    dev_reg = device_registry.async_get(hass)
    entries = device_registry.async_entries_for_label(dev_reg, _label_id)
    return [entry.id for entry in entries]


def label_entities(hass: HomeAssistant, label_id_or_name: str) -> Iterable[str]:
    """Return entities for a given label ID or name."""
    if (_label_id := _label_id_or_name(hass, label_id_or_name)) is None:
        return []
    ent_reg = entity_registry.async_get(hass)
    entries = entity_registry.async_entries_for_label(ent_reg, _label_id)
    return [entry.entity_id for entry in entries]


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
        if isinstance(value, str) and not valid_entity_id(value):
            point_state = None
        else:
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
                    "Distance:State does not contain valid location: %s", point_state
                )
                return None

            latitude = point_state.attributes.get(ATTR_LATITUDE)
            longitude = point_state.attributes.get(ATTR_LONGITUDE)

        locations.append((latitude, longitude))

    if len(locations) == 1:
        return hass.config.distance(*locations[0])

    return hass.config.units.length(
        loc_util.distance(*locations[0] + locations[1]), UnitOfLength.METERS
    )


def is_hidden_entity(hass: HomeAssistant, entity_id: str) -> bool:
    """Test if an entity is hidden."""
    entity_reg = entity_registry.async_get(hass)
    entry = entity_reg.async_get(entity_id)
    return entry is not None and entry.hidden


def is_state(hass: HomeAssistant, entity_id: str, state: str | list[str]) -> bool:
    """Test if a state is a specific value."""
    state_obj = _get_state(hass, entity_id)
    return state_obj is not None and (
        state_obj.state == state or isinstance(state, list) and state_obj.state in state
    )


def is_state_attr(hass: HomeAssistant, entity_id: str, name: str, value: Any) -> bool:
    """Test if a state's attribute is a specific value."""
    attr = state_attr(hass, entity_id, name)
    return attr is not None and attr == value


def state_attr(hass: HomeAssistant, entity_id: str, name: str) -> Any:
    """Get a specific attribute from a state."""
    if (state_obj := _get_state(hass, entity_id)) is not None:
        return state_obj.attributes.get(name)
    return None


def has_value(hass: HomeAssistant, entity_id: str) -> bool:
    """Test if an entity has a valid value."""
    state_obj = _get_state(hass, entity_id)

    return state_obj is not None and (
        state_obj.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]
    )


def now(hass: HomeAssistant) -> datetime:
    """Record fetching now."""
    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    return dt_util.now()


def utcnow(hass: HomeAssistant) -> datetime:
    """Record fetching utcnow."""
    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    return dt_util.utcnow()


def raise_no_default(function: str, value: Any) -> NoReturn:
    """Log warning if no default is specified."""
    template, action = template_cv.get() or ("", "rendering or compiling")
    raise ValueError(
        f"Template error: {function} got invalid input '{value}' when {action} template"
        f" '{template}' but no default was specified"
    )


def forgiving_round(value, precision=0, method="common", default=_SENTINEL):
    """Filter to round a value."""
    try:
        # support rounding methods like jinja
        multiplier = float(10**precision)
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
        if default is _SENTINEL:
            raise_no_default("round", value)
        return default


def multiply(value, amount, default=_SENTINEL):
    """Filter to convert value to float and multiply it."""
    try:
        return float(value) * amount
    except (ValueError, TypeError):
        # If value can't be converted to float
        if default is _SENTINEL:
            raise_no_default("multiply", value)
        return default


def add(value, amount, default=_SENTINEL):
    """Filter to convert value to float and add it."""
    try:
        return float(value) + amount
    except (ValueError, TypeError):
        # If value can't be converted to float
        if default is _SENTINEL:
            raise_no_default("add", value)
        return default


def logarithm(value, base=math.e, default=_SENTINEL):
    """Filter and function to get logarithm of the value with a specific base."""
    try:
        base_float = float(base)
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("log", base)
        return default
    try:
        value_float = float(value)
        return math.log(value_float, base_float)
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("log", value)
        return default


def sine(value, default=_SENTINEL):
    """Filter and function to get sine of the value."""
    try:
        return math.sin(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("sin", value)
        return default


def cosine(value, default=_SENTINEL):
    """Filter and function to get cosine of the value."""
    try:
        return math.cos(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("cos", value)
        return default


def tangent(value, default=_SENTINEL):
    """Filter and function to get tangent of the value."""
    try:
        return math.tan(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("tan", value)
        return default


def arc_sine(value, default=_SENTINEL):
    """Filter and function to get arc sine of the value."""
    try:
        return math.asin(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("asin", value)
        return default


def arc_cosine(value, default=_SENTINEL):
    """Filter and function to get arc cosine of the value."""
    try:
        return math.acos(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("acos", value)
        return default


def arc_tangent(value, default=_SENTINEL):
    """Filter and function to get arc tangent of the value."""
    try:
        return math.atan(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("atan", value)
        return default


def arc_tangent2(*args, default=_SENTINEL):
    """Filter and function to calculate four quadrant arc tangent of y / x.

    The parameters to atan2 may be passed either in an iterable or as separate arguments
    The default value may be passed either as a positional or in a keyword argument
    """
    try:
        if 1 <= len(args) <= 2 and isinstance(args[0], (list, tuple)):
            if len(args) == 2 and default is _SENTINEL:
                # Default value passed as a positional argument
                default = args[1]
            args = args[0]
        elif len(args) == 3 and default is _SENTINEL:
            # Default value passed as a positional argument
            default = args[2]

        return math.atan2(float(args[0]), float(args[1]))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("atan2", args)
        return default


def version(value):
    """Filter and function to get version object of the value."""
    return AwesomeVersion(value)


def square_root(value, default=_SENTINEL):
    """Filter and function to get square root of the value."""
    try:
        return math.sqrt(float(value))
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("sqrt", value)
        return default


def timestamp_custom(value, date_format=DATE_STR_FORMAT, local=True, default=_SENTINEL):
    """Filter to convert given timestamp to format."""
    try:
        result = dt_util.utc_from_timestamp(value)

        if local:
            result = dt_util.as_local(result)

        return result.strftime(date_format)
    except (ValueError, TypeError):
        # If timestamp can't be converted
        if default is _SENTINEL:
            raise_no_default("timestamp_custom", value)
        return default


def timestamp_local(value, default=_SENTINEL):
    """Filter to convert given timestamp to local date/time."""
    try:
        return dt_util.as_local(dt_util.utc_from_timestamp(value)).isoformat()
    except (ValueError, TypeError):
        # If timestamp can't be converted
        if default is _SENTINEL:
            raise_no_default("timestamp_local", value)
        return default


def timestamp_utc(value, default=_SENTINEL):
    """Filter to convert given timestamp to UTC date/time."""
    try:
        return dt_util.utc_from_timestamp(value).isoformat()
    except (ValueError, TypeError):
        # If timestamp can't be converted
        if default is _SENTINEL:
            raise_no_default("timestamp_utc", value)
        return default


def forgiving_as_timestamp(value, default=_SENTINEL):
    """Filter and function which tries to convert value to timestamp."""
    try:
        return dt_util.as_timestamp(value)
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("as_timestamp", value)
        return default


def as_datetime(value: Any, default: Any = _SENTINEL) -> Any:
    """Filter and to convert a time string or UNIX timestamp to datetime object."""
    # Return datetime.datetime object without changes
    if type(value) is datetime:
        return value
    # Add midnight to datetime.date object
    if type(value) is date:
        return datetime.combine(value, time(0, 0, 0))
    try:
        # Check for a valid UNIX timestamp string, int or float
        timestamp = float(value)
        return dt_util.utc_from_timestamp(timestamp)
    except (ValueError, TypeError):
        # Try to parse datetime string to datetime object
        try:
            return dt_util.parse_datetime(value, raise_on_error=True)
        except (ValueError, TypeError):
            if default is _SENTINEL:
                # Return None on string input
                # to ensure backwards compatibility with HA Core 2024.1 and before.
                if isinstance(value, str):
                    return None
                raise_no_default("as_datetime", value)
            return default


def as_timedelta(value: str) -> timedelta | None:
    """Parse a ISO8601 duration like 'PT10M' to a timedelta."""
    return dt_util.parse_duration(value)


def merge_response(value: ServiceResponse) -> list[Any]:
    """Merge action responses into single list.

    Checks that the input is a correct service response:
    {
        "entity_id": {str: dict[str, Any]},
    }
    If response is a single list, it will extend the list with the items
        and add the entity_id and value_key to each dictionary for reference.
    If response is a dictionary or multiple lists,
        it will append the dictionary/lists to the list
        and add the entity_id to each dictionary for reference.
    """
    if not isinstance(value, dict):
        raise TypeError("Response is not a dictionary")
    if not value:
        # Bail out early if response is an empty dictionary
        return []

    is_single_list = False
    response_items: list = []
    input_service_response = deepcopy(value)
    for entity_id, entity_response in input_service_response.items():  # pylint: disable=too-many-nested-blocks
        if not isinstance(entity_response, dict):
            raise TypeError("Response is not a dictionary")
        for value_key, type_response in entity_response.items():
            if len(entity_response) == 1 and isinstance(type_response, list):
                # Provides special handling for responses such as calendar events
                # and weather forecasts where the response contains a single list with multiple
                # dictionaries inside.
                is_single_list = True
                for dict_in_list in type_response:
                    if isinstance(dict_in_list, dict):
                        if ATTR_ENTITY_ID in dict_in_list:
                            raise ValueError(
                                f"Response dictionary already contains key '{ATTR_ENTITY_ID}'"
                            )
                        dict_in_list[ATTR_ENTITY_ID] = entity_id
                        dict_in_list["value_key"] = value_key
                response_items.extend(type_response)
            else:
                # Break the loop if not a single list as the logic is then managed in the outer loop
                # which handles both dictionaries and in the case of multiple lists.
                break

        if not is_single_list:
            _response = entity_response.copy()
            if ATTR_ENTITY_ID in _response:
                raise ValueError(
                    f"Response dictionary already contains key '{ATTR_ENTITY_ID}'"
                )
            _response[ATTR_ENTITY_ID] = entity_id
            response_items.append(_response)

    return response_items


def strptime(string, fmt, default=_SENTINEL):
    """Parse a time string to datetime."""
    try:
        return datetime.strptime(string, fmt)
    except (ValueError, AttributeError, TypeError):
        if default is _SENTINEL:
            raise_no_default("strptime", string)
        return default


def fail_when_undefined(value):
    """Filter to force a failure when the value is undefined."""
    if isinstance(value, jinja2.Undefined):
        value()
    return value


def min_max_from_filter(builtin_filter: Any, name: str) -> Any:
    """Convert a built-in min/max Jinja filter to a global function.

    The parameters may be passed as an iterable or as separate arguments.
    """

    @pass_environment
    @wraps(builtin_filter)
    def wrapper(environment: jinja2.Environment, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 0:
            raise TypeError(f"{name} expected at least 1 argument, got 0")

        if len(args) == 1:
            if isinstance(args[0], Iterable):
                return builtin_filter(environment, args[0], **kwargs)

            raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")

        return builtin_filter(environment, args, **kwargs)

    return pass_environment(wrapper)


def average(*args: Any, default: Any = _SENTINEL) -> Any:
    """Filter and function to calculate the arithmetic mean.

    Calculates of an iterable or of two or more arguments.

    The parameters may be passed as an iterable or as separate arguments.
    """
    if len(args) == 0:
        raise TypeError("average expected at least 1 argument, got 0")

    # If first argument is iterable and more than 1 argument provided but not a named
    # default, then use 2nd argument as default.
    if isinstance(args[0], Iterable):
        average_list = args[0]
        if len(args) > 1 and default is _SENTINEL:
            default = args[1]
    elif len(args) == 1:
        raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
    else:
        average_list = args

    try:
        return statistics.fmean(average_list)
    except (TypeError, statistics.StatisticsError):
        if default is _SENTINEL:
            raise_no_default("average", args)
        return default


def median(*args: Any, default: Any = _SENTINEL) -> Any:
    """Filter and function to calculate the median.

    Calculates median of an iterable of two or more arguments.

    The parameters may be passed as an iterable or as separate arguments.
    """
    if len(args) == 0:
        raise TypeError("median expected at least 1 argument, got 0")

    # If first argument is a list or tuple and more than 1 argument provided but not a named
    # default, then use 2nd argument as default.
    if isinstance(args[0], Iterable):
        median_list = args[0]
        if len(args) > 1 and default is _SENTINEL:
            default = args[1]
    elif len(args) == 1:
        raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
    else:
        median_list = args

    try:
        return statistics.median(median_list)
    except (TypeError, statistics.StatisticsError):
        if default is _SENTINEL:
            raise_no_default("median", args)
        return default


def statistical_mode(*args: Any, default: Any = _SENTINEL) -> Any:
    """Filter and function to calculate the statistical mode.

    Calculates mode of an iterable of two or more arguments.

    The parameters may be passed as an iterable or as separate arguments.
    """
    if not args:
        raise TypeError("statistical_mode expected at least 1 argument, got 0")

    # If first argument is a list or tuple and more than 1 argument provided but not a named
    # default, then use 2nd argument as default.
    if len(args) == 1 and isinstance(args[0], Iterable):
        mode_list = args[0]
    elif isinstance(args[0], list | tuple):
        mode_list = args[0]
        if len(args) > 1 and default is _SENTINEL:
            default = args[1]
    elif len(args) == 1:
        raise TypeError(f"'{type(args[0]).__name__}' object is not iterable")
    else:
        mode_list = args

    try:
        return statistics.mode(mode_list)
    except (TypeError, statistics.StatisticsError):
        if default is _SENTINEL:
            raise_no_default("statistical_mode", args)
        return default


def forgiving_float(value, default=_SENTINEL):
    """Try to convert value to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("float", value)
        return default


def forgiving_float_filter(value, default=_SENTINEL):
    """Try to convert value to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        if default is _SENTINEL:
            raise_no_default("float", value)
        return default


def forgiving_int(value, default=_SENTINEL, base=10):
    """Try to convert value to an int, and raise if it fails."""
    result = jinja2.filters.do_int(value, default=default, base=base)
    if result is _SENTINEL:
        raise_no_default("int", value)
    return result


def forgiving_int_filter(value, default=_SENTINEL, base=10):
    """Try to convert value to an int, and raise if it fails."""
    result = jinja2.filters.do_int(value, default=default, base=base)
    if result is _SENTINEL:
        raise_no_default("int", value)
    return result


def is_number(value):
    """Try to convert value to a float."""
    try:
        fvalue = float(value)
    except (ValueError, TypeError):
        return False
    if not math.isfinite(fvalue):
        return False
    return True


def _is_list(value: Any) -> bool:
    """Return whether a value is a list."""
    return isinstance(value, list)


def _is_set(value: Any) -> bool:
    """Return whether a value is a set."""
    return isinstance(value, set)


def _is_tuple(value: Any) -> bool:
    """Return whether a value is a tuple."""
    return isinstance(value, tuple)


def _to_set(value: Any) -> set[Any]:
    """Convert value to set."""
    return set(value)


def _to_tuple(value):
    """Convert value to tuple."""
    return tuple(value)


def _is_datetime(value: Any) -> bool:
    """Return whether a value is a datetime."""
    return isinstance(value, datetime)


def _is_string_like(value: Any) -> bool:
    """Return whether a value is a string or string like object."""
    return isinstance(value, (str, bytes, bytearray))


def regex_match(value, find="", ignorecase=False):
    """Match value using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.IGNORECASE if ignorecase else 0
    return bool(_regex_cache(find, flags).match(value))


_regex_cache = lru_cache(maxsize=128)(re.compile)


def regex_replace(value="", find="", replace="", ignorecase=False):
    """Replace using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.IGNORECASE if ignorecase else 0
    return _regex_cache(find, flags).sub(replace, value)


def regex_search(value, find="", ignorecase=False):
    """Search using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.IGNORECASE if ignorecase else 0
    return bool(_regex_cache(find, flags).search(value))


def regex_findall_index(value, find="", index=0, ignorecase=False):
    """Find all matches using regex and then pick specific match index."""
    return regex_findall(value, find, ignorecase)[index]


def regex_findall(value, find="", ignorecase=False):
    """Find all matches using regex."""
    if not isinstance(value, str):
        value = str(value)
    flags = re.IGNORECASE if ignorecase else 0
    return _regex_cache(find, flags).findall(value)


def bitwise_and(first_value, second_value):
    """Perform a bitwise and operation."""
    return first_value & second_value


def bitwise_or(first_value, second_value):
    """Perform a bitwise or operation."""
    return first_value | second_value


def bitwise_xor(first_value, second_value):
    """Perform a bitwise xor operation."""
    return first_value ^ second_value


def struct_pack(value: Any | None, format_string: str) -> bytes | None:
    """Pack an object into a bytes object."""
    try:
        return pack(format_string, value)
    except StructError:
        _LOGGER.warning(
            (
                "Template warning: 'pack' unable to pack object '%s' with type '%s' and"
                " format_string '%s' see https://docs.python.org/3/library/struct.html"
                " for more information"
            ),
            str(value),
            type(value).__name__,
            format_string,
        )
        return None


def struct_unpack(value: bytes, format_string: str, offset: int = 0) -> Any | None:
    """Unpack an object from bytes an return the first native object."""
    try:
        return unpack_from(format_string, value, offset)[0]
    except StructError:
        _LOGGER.warning(
            (
                "Template warning: 'unpack' unable to unpack object '%s' with"
                " format_string '%s' and offset %s see"
                " https://docs.python.org/3/library/struct.html for more information"
            ),
            value,
            format_string,
            offset,
        )
        return None


def base64_encode(value: str) -> str:
    """Perform base64 encode."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def base64_decode(value: str, encoding: str | None = "utf-8") -> str | bytes:
    """Perform base64 decode."""
    decoded = base64.b64decode(value)
    if encoding:
        return decoded.decode(encoding)

    return decoded


def ordinal(value):
    """Perform ordinal conversion."""
    suffixes = ["th", "st", "nd", "rd"] + ["th"] * 6  # codespell:ignore nd
    return str(value) + (
        suffixes[(int(str(value)[-1])) % 10]
        if int(str(value)[-2:]) % 100 not in range(11, 14)
        else "th"
    )


def from_json(value):
    """Convert a JSON string to an object."""
    return json_loads(value)


def _to_json_default(obj: Any) -> None:
    """Disable custom types in json serialization."""
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def to_json(
    value: Any,
    ensure_ascii: bool = False,
    pretty_print: bool = False,
    sort_keys: bool = False,
) -> str:
    """Convert an object to a JSON string."""
    if ensure_ascii:
        # For those who need ascii, we can't use orjson, so we fall back to the json library.
        return json.dumps(
            value,
            ensure_ascii=ensure_ascii,
            indent=2 if pretty_print else None,
            sort_keys=sort_keys,
        )

    option = (
        ORJSON_PASSTHROUGH_OPTIONS
        # OPT_NON_STR_KEYS is added as a workaround to
        # ensure subclasses of str are allowed as dict keys
        # See: https://github.com/ijl/orjson/issues/445
        | orjson.OPT_NON_STR_KEYS
        | (orjson.OPT_INDENT_2 if pretty_print else 0)
        | (orjson.OPT_SORT_KEYS if sort_keys else 0)
    )

    return orjson.dumps(
        value,
        option=option,
        default=_to_json_default,
    ).decode("utf-8")


@pass_context
def random_every_time(context, values):
    """Choose a random value.

    Unlike Jinja's random filter,
    this is context-dependent to avoid caching the chosen value.
    """
    return random.choice(values)


def today_at(hass: HomeAssistant, time_str: str = "") -> datetime:
    """Record fetching now where the time has been replaced with value."""
    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    today = dt_util.start_of_local_day()
    if not time_str:
        return today

    if (time_today := dt_util.parse_time(time_str)) is None:
        raise ValueError(
            f"could not convert {type(time_str).__name__} to datetime: '{time_str}'"
        )

    return datetime.combine(today, time_today, today.tzinfo)


def relative_time(hass: HomeAssistant, value: Any) -> Any:
    """Take a datetime and return its "age" as a string.

    The age can be in second, minute, hour, day, month or year. Only the
    biggest unit is considered, e.g. if it's 2 days and 3 hours, "2 days" will
    be returned.
    If the input datetime is in the future,
    the input datetime will be returned.

    If the input are not a datetime object the input will be returned unmodified.

    Note: This template function is deprecated in favor of `time_until`, but is still
    supported so as not to break old templates.
    """

    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    if not isinstance(value, datetime):
        return value
    if not value.tzinfo:
        value = dt_util.as_local(value)
    if dt_util.now() < value:
        return value
    return dt_util.get_age(value)


def time_since(hass: HomeAssistant, value: Any | datetime, precision: int = 1) -> Any:
    """Take a datetime and return its "age" as a string.

    The age can be in seconds, minutes, hours, days, months and year.

    precision is the number of units to return, with the last unit rounded.

    If the value not a datetime object the input will be returned unmodified.
    """
    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    if not isinstance(value, datetime):
        return value
    if not value.tzinfo:
        value = dt_util.as_local(value)
    if dt_util.now() < value:
        return value

    return dt_util.get_age(value, precision)


def time_until(hass: HomeAssistant, value: Any | datetime, precision: int = 1) -> Any:
    """Take a datetime and return the amount of time until that time as a string.

    The time until can be in seconds, minutes, hours, days, months and years.

    precision is the number of units to return, with the last unit rounded.

    If the value not a datetime object the input will be returned unmodified.
    """
    if (render_info := _render_info.get()) is not None:
        render_info.has_time = True

    if not isinstance(value, datetime):
        return value
    if not value.tzinfo:
        value = dt_util.as_local(value)
    if dt_util.now() > value:
        return value

    return dt_util.get_time_remaining(value, precision)


def urlencode(value):
    """Urlencode dictionary and return as UTF-8 string."""
    return urllib_urlencode(value).encode("utf-8")


def slugify(value, separator="_"):
    """Convert a string into a slug, such as what is used for entity ids."""
    return slugify_util(value, separator=separator)


def iif(
    value: Any, if_true: Any = True, if_false: Any = False, if_none: Any = _SENTINEL
) -> Any:
    """Immediate if function/filter that allow for common if/else constructs.

    https://en.wikipedia.org/wiki/IIf

    Examples:
        {{ is_state("device_tracker.frenck", "home") | iif("yes", "no") }}
        {{ iif(1==2, "yes", "no") }}
        {{ (1 == 1) | iif("yes", "no") }}

    """
    if value is None and if_none is not _SENTINEL:
        return if_none
    if bool(value):
        return if_true
    return if_false


class TemplateContextManager(AbstractContextManager):
    """Context manager to store template being parsed or rendered in a ContextVar."""

    def set_template(self, template_str: str, action: str) -> None:
        """Store template being parsed or rendered in a Contextvar to aid error handling."""
        template_cv.set((template_str, action))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Raise any exception triggered within the runtime context."""
        template_cv.set(None)


_template_context_manager = TemplateContextManager()


def _render_with_context(
    template_str: str, template: jinja2.Template, **kwargs: Any
) -> str:
    """Store template being rendered in a ContextVar to aid error handling."""
    with _template_context_manager as cm:
        cm.set_template(template_str, "rendering")
        return template.render(**kwargs)


def make_logging_undefined(
    strict: bool | None, log_fn: Callable[[int, str], None] | None
) -> type[jinja2.Undefined]:
    """Log on undefined variables."""

    if strict:
        return jinja2.StrictUndefined

    def _log_with_logger(level: int, msg: str) -> None:
        template, action = template_cv.get() or ("", "rendering or compiling")
        _LOGGER.log(
            level,
            "Template variable %s: %s when %s '%s'",
            logging.getLevelName(level).lower(),
            msg,
            action,
            template,
        )

    _log_fn = log_fn or _log_with_logger

    class LoggingUndefined(jinja2.Undefined):
        """Log on undefined variables."""

        def _log_message(self) -> None:
            _log_fn(logging.WARNING, self._undefined_message)

        def _fail_with_undefined_error(self, *args, **kwargs):
            try:
                return super()._fail_with_undefined_error(*args, **kwargs)
            except self._undefined_exception:
                _log_fn(logging.ERROR, self._undefined_message)
                raise

        def __str__(self) -> str:
            """Log undefined __str___."""
            self._log_message()
            return super().__str__()

        def __iter__(self):
            """Log undefined __iter___."""
            self._log_message()
            return super().__iter__()

        def __bool__(self) -> bool:
            """Log undefined __bool___."""
            self._log_message()
            return super().__bool__()

    return LoggingUndefined


async def async_load_custom_templates(hass: HomeAssistant) -> None:
    """Load all custom jinja files under 5MiB into memory."""
    custom_templates = await hass.async_add_executor_job(_load_custom_templates, hass)
    _get_hass_loader(hass).sources = custom_templates


def _load_custom_templates(hass: HomeAssistant) -> dict[str, str]:
    result = {}
    jinja_path = hass.config.path("custom_templates")
    all_files = [
        item
        for item in pathlib.Path(jinja_path).rglob("*.jinja")
        if item.is_file() and item.stat().st_size <= MAX_CUSTOM_TEMPLATE_SIZE
    ]
    for file in all_files:
        content = file.read_text()
        path = str(file.relative_to(jinja_path))
        result[path] = content
    return result


@singleton(_HASS_LOADER)
def _get_hass_loader(hass: HomeAssistant) -> HassLoader:
    return HassLoader({})


class HassLoader(jinja2.BaseLoader):
    """An in-memory jinja loader that keeps track of templates that need to be reloaded."""

    def __init__(self, sources: dict[str, str]) -> None:
        """Initialize an empty HassLoader."""
        self._sources = sources
        self._reload = 0

    @property
    def sources(self) -> dict[str, str]:
        """Map filename to jinja source."""
        return self._sources

    @sources.setter
    def sources(self, value: dict[str, str]) -> None:
        self._sources = value
        self._reload += 1

    def get_source(
        self, environment: jinja2.Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        """Get in-memory sources."""
        if template not in self._sources:
            raise jinja2.TemplateNotFound(template)
        cur_reload = self._reload
        return self._sources[template], template, lambda: cur_reload == self._reload


class TemplateEnvironment(ImmutableSandboxedEnvironment):
    """The Home Assistant template environment."""

    def __init__(
        self,
        hass: HomeAssistant | None,
        limited: bool | None = False,
        strict: bool | None = False,
        log_fn: Callable[[int, str], None] | None = None,
    ) -> None:
        """Initialise template environment."""
        super().__init__(undefined=make_logging_undefined(strict, log_fn))
        self.hass = hass
        self.template_cache: weakref.WeakValueDictionary[
            str | jinja2.nodes.Template, CodeType | None
        ] = weakref.WeakValueDictionary()
        self.add_extension("jinja2.ext.loopcontrols")
        self.filters["round"] = forgiving_round
        self.filters["multiply"] = multiply
        self.filters["add"] = add
        self.filters["log"] = logarithm
        self.filters["sin"] = sine
        self.filters["cos"] = cosine
        self.filters["tan"] = tangent
        self.filters["asin"] = arc_sine
        self.filters["acos"] = arc_cosine
        self.filters["atan"] = arc_tangent
        self.filters["atan2"] = arc_tangent2
        self.filters["sqrt"] = square_root
        self.filters["as_datetime"] = as_datetime
        self.filters["as_timedelta"] = as_timedelta
        self.filters["as_timestamp"] = forgiving_as_timestamp
        self.filters["as_local"] = dt_util.as_local
        self.filters["timestamp_custom"] = timestamp_custom
        self.filters["timestamp_local"] = timestamp_local
        self.filters["timestamp_utc"] = timestamp_utc
        self.filters["to_json"] = to_json
        self.filters["from_json"] = from_json
        self.filters["is_defined"] = fail_when_undefined
        self.filters["average"] = average
        self.filters["median"] = median
        self.filters["statistical_mode"] = statistical_mode
        self.filters["random"] = random_every_time
        self.filters["base64_encode"] = base64_encode
        self.filters["base64_decode"] = base64_decode
        self.filters["ordinal"] = ordinal
        self.filters["regex_match"] = regex_match
        self.filters["regex_replace"] = regex_replace
        self.filters["regex_search"] = regex_search
        self.filters["regex_findall"] = regex_findall
        self.filters["regex_findall_index"] = regex_findall_index
        self.filters["bitwise_and"] = bitwise_and
        self.filters["bitwise_or"] = bitwise_or
        self.filters["bitwise_xor"] = bitwise_xor
        self.filters["pack"] = struct_pack
        self.filters["unpack"] = struct_unpack
        self.filters["ord"] = ord
        self.filters["is_number"] = is_number
        self.filters["float"] = forgiving_float_filter
        self.filters["int"] = forgiving_int_filter
        self.filters["slugify"] = slugify
        self.filters["iif"] = iif
        self.filters["bool"] = forgiving_boolean
        self.filters["version"] = version
        self.filters["contains"] = contains
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
        self.globals["as_datetime"] = as_datetime
        self.globals["as_local"] = dt_util.as_local
        self.globals["as_timedelta"] = as_timedelta
        self.globals["as_timestamp"] = forgiving_as_timestamp
        self.globals["timedelta"] = timedelta
        self.globals["merge_response"] = merge_response
        self.globals["strptime"] = strptime
        self.globals["urlencode"] = urlencode
        self.globals["average"] = average
        self.globals["median"] = median
        self.globals["statistical_mode"] = statistical_mode
        self.globals["max"] = min_max_from_filter(self.filters["max"], "max")
        self.globals["min"] = min_max_from_filter(self.filters["min"], "min")
        self.globals["is_number"] = is_number
        self.globals["set"] = _to_set
        self.globals["tuple"] = _to_tuple
        self.globals["int"] = forgiving_int
        self.globals["pack"] = struct_pack
        self.globals["unpack"] = struct_unpack
        self.globals["slugify"] = slugify
        self.globals["iif"] = iif
        self.globals["bool"] = forgiving_boolean
        self.globals["version"] = version
        self.globals["zip"] = zip
        self.tests["is_number"] = is_number
        self.tests["list"] = _is_list
        self.tests["set"] = _is_set
        self.tests["tuple"] = _is_tuple
        self.tests["datetime"] = _is_datetime
        self.tests["string_like"] = _is_string_like
        self.tests["match"] = regex_match
        self.tests["search"] = regex_search
        self.tests["contains"] = contains

        if hass is None:
            return

        # This environment has access to hass, attach its loader to enable imports.
        self.loader = _get_hass_loader(hass)

        # We mark these as a context functions to ensure they get
        # evaluated fresh with every execution, rather than executed
        # at compile time and the value stored. The context itself
        # can be discarded, we only need to get at the hass object.
        def hassfunction[**_P, _R](
            func: Callable[Concatenate[HomeAssistant, _P], _R],
            jinja_context: Callable[
                [Callable[Concatenate[Any, _P], _R]],
                Callable[Concatenate[Any, _P], _R],
            ] = pass_context,
        ) -> Callable[Concatenate[Any, _P], _R]:
            """Wrap function that depend on hass."""

            @wraps(func)
            def wrapper(_: Any, *args: _P.args, **kwargs: _P.kwargs) -> _R:
                return func(hass, *args, **kwargs)

            return jinja_context(wrapper)

        self.globals["device_entities"] = hassfunction(device_entities)
        self.filters["device_entities"] = self.globals["device_entities"]

        self.globals["device_attr"] = hassfunction(device_attr)
        self.filters["device_attr"] = self.globals["device_attr"]

        self.globals["config_entry_attr"] = hassfunction(config_entry_attr)
        self.filters["config_entry_attr"] = self.globals["config_entry_attr"]

        self.globals["is_device_attr"] = hassfunction(is_device_attr)
        self.tests["is_device_attr"] = hassfunction(is_device_attr, pass_eval_context)

        self.globals["config_entry_id"] = hassfunction(config_entry_id)
        self.filters["config_entry_id"] = self.globals["config_entry_id"]

        self.globals["device_id"] = hassfunction(device_id)
        self.filters["device_id"] = self.globals["device_id"]

        self.globals["issues"] = hassfunction(issues)

        self.globals["issue"] = hassfunction(issue)
        self.filters["issue"] = self.globals["issue"]

        self.globals["areas"] = hassfunction(areas)

        self.globals["area_id"] = hassfunction(area_id)
        self.filters["area_id"] = self.globals["area_id"]

        self.globals["area_name"] = hassfunction(area_name)
        self.filters["area_name"] = self.globals["area_name"]

        self.globals["area_entities"] = hassfunction(area_entities)
        self.filters["area_entities"] = self.globals["area_entities"]

        self.globals["area_devices"] = hassfunction(area_devices)
        self.filters["area_devices"] = self.globals["area_devices"]

        self.globals["floors"] = hassfunction(floors)
        self.filters["floors"] = self.globals["floors"]

        self.globals["floor_id"] = hassfunction(floor_id)
        self.filters["floor_id"] = self.globals["floor_id"]

        self.globals["floor_name"] = hassfunction(floor_name)
        self.filters["floor_name"] = self.globals["floor_name"]

        self.globals["floor_areas"] = hassfunction(floor_areas)
        self.filters["floor_areas"] = self.globals["floor_areas"]

        self.globals["integration_entities"] = hassfunction(integration_entities)
        self.filters["integration_entities"] = self.globals["integration_entities"]

        self.globals["labels"] = hassfunction(labels)
        self.filters["labels"] = self.globals["labels"]

        self.globals["label_id"] = hassfunction(label_id)
        self.filters["label_id"] = self.globals["label_id"]

        self.globals["label_name"] = hassfunction(label_name)
        self.filters["label_name"] = self.globals["label_name"]

        self.globals["label_areas"] = hassfunction(label_areas)
        self.filters["label_areas"] = self.globals["label_areas"]

        self.globals["label_devices"] = hassfunction(label_devices)
        self.filters["label_devices"] = self.globals["label_devices"]

        self.globals["label_entities"] = hassfunction(label_entities)
        self.filters["label_entities"] = self.globals["label_entities"]

        if limited:
            # Only device_entities is available to limited templates, mark other
            # functions and filters as unsupported.
            def unsupported(name: str) -> Callable[[], NoReturn]:
                def warn_unsupported(*args: Any, **kwargs: Any) -> NoReturn:
                    raise TemplateError(
                        f"Use of '{name}' is not supported in limited templates"
                    )

                return warn_unsupported

            hass_globals = [
                "closest",
                "distance",
                "expand",
                "is_hidden_entity",
                "is_state",
                "is_state_attr",
                "state_attr",
                "states",
                "state_translated",
                "has_value",
                "utcnow",
                "now",
                "device_attr",
                "is_device_attr",
                "device_id",
                "area_id",
                "area_name",
                "floor_id",
                "floor_name",
                "relative_time",
                "time_since",
                "time_until",
                "today_at",
                "label_id",
                "label_name",
            ]
            hass_filters = [
                "closest",
                "expand",
                "device_id",
                "area_id",
                "area_name",
                "floor_id",
                "floor_name",
                "has_value",
                "label_id",
                "label_name",
            ]
            hass_tests = [
                "has_value",
                "is_hidden_entity",
                "is_state",
                "is_state_attr",
            ]
            for glob in hass_globals:
                self.globals[glob] = unsupported(glob)
            for filt in hass_filters:
                self.filters[filt] = unsupported(filt)
            for test in hass_tests:
                self.filters[test] = unsupported(test)
            return

        self.globals["expand"] = hassfunction(expand)
        self.filters["expand"] = self.globals["expand"]
        self.globals["closest"] = hassfunction(closest)
        self.filters["closest"] = hassfunction(closest_filter)
        self.globals["distance"] = hassfunction(distance)
        self.globals["is_hidden_entity"] = hassfunction(is_hidden_entity)
        self.tests["is_hidden_entity"] = hassfunction(
            is_hidden_entity, pass_eval_context
        )
        self.globals["is_state"] = hassfunction(is_state)
        self.tests["is_state"] = hassfunction(is_state, pass_eval_context)
        self.globals["is_state_attr"] = hassfunction(is_state_attr)
        self.tests["is_state_attr"] = hassfunction(is_state_attr, pass_eval_context)
        self.globals["state_attr"] = hassfunction(state_attr)
        self.filters["state_attr"] = self.globals["state_attr"]
        self.globals["states"] = AllStates(hass)
        self.filters["states"] = self.globals["states"]
        self.globals["state_translated"] = StateTranslated(hass)
        self.filters["state_translated"] = self.globals["state_translated"]
        self.globals["has_value"] = hassfunction(has_value)
        self.filters["has_value"] = self.globals["has_value"]
        self.tests["has_value"] = hassfunction(has_value, pass_eval_context)
        self.globals["utcnow"] = hassfunction(utcnow)
        self.globals["now"] = hassfunction(now)
        self.globals["relative_time"] = hassfunction(relative_time)
        self.filters["relative_time"] = self.globals["relative_time"]
        self.globals["time_since"] = hassfunction(time_since)
        self.filters["time_since"] = self.globals["time_since"]
        self.globals["time_until"] = hassfunction(time_until)
        self.filters["time_until"] = self.globals["time_until"]
        self.globals["today_at"] = hassfunction(today_at)
        self.filters["today_at"] = self.globals["today_at"]

    def is_safe_callable(self, obj):
        """Test if callback is safe."""
        return isinstance(
            obj, (AllStates, StateTranslated)
        ) or super().is_safe_callable(obj)

    def is_safe_attribute(self, obj, attr, value):
        """Test if attribute is safe."""
        if isinstance(
            obj, (AllStates, DomainStates, TemplateState, LoopContext, AsyncLoopContext)
        ):
            return attr[0] != "_"

        if isinstance(obj, Namespace):
            return True

        return super().is_safe_attribute(obj, attr, value)

    @overload
    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: Literal[False] = False,
        defer_init: bool = False,
    ) -> CodeType: ...

    @overload
    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: Literal[True] = ...,
        defer_init: bool = False,
    ) -> str: ...

    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: bool = False,
        defer_init: bool = False,
    ) -> CodeType | str:
        """Compile the template."""
        if (
            name is not None
            or filename is not None
            or raw is not False
            or defer_init is not False
        ):
            # If there are any non-default keywords args, we do
            # not cache.  In prodution we currently do not have
            # any instance of this.
            return super().compile(  # type: ignore[no-any-return,call-overload]
                source,
                name,
                filename,
                raw,
                defer_init,
            )

        compiled = super().compile(source)
        self.template_cache[source] = compiled
        return compiled


_NO_HASS_ENV = TemplateEnvironment(None)
