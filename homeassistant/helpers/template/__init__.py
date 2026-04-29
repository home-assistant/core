"""Template helper methods for rendering strings with Home Assistant data."""

from __future__ import annotations

from ast import literal_eval
import asyncio
import collections.abc
from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache, partial
import logging
import pathlib
import re
import sys
from types import CodeType
from typing import TYPE_CHECKING, Any, Literal, Self, overload
import weakref

import jinja2
from jinja2.runtime import AsyncLoopContext, LoopContext
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jinja2.utils import Namespace

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads
from homeassistant.util.thread import ThreadWithException

from .context import (
    TemplateContextManager as TemplateContextManager,
    render_with_context,
    template_context_manager,
    template_cv,
)
from .helpers import result_as_boolean as result_as_boolean
from .render_info import RenderInfo, render_info_cv
from .states import (
    CACHED_TEMPLATE_LRU,
    CACHED_TEMPLATE_NO_COLLECT_LRU,
    ENTITY_COUNT_GROWTH_FACTOR,
    AllStates,
    DomainStates,
    StateAttrTranslated,
    StateTranslated,
    TemplateState as TemplateState,
    TemplateStateFromEntityId as TemplateStateFromEntityId,
)

if TYPE_CHECKING:
    from _typeshed import OptExcInfo

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

EVAL_CACHE_SIZE = 512

MAX_CUSTOM_TEMPLATE_SIZE = 5 * 1024 * 1024
MAX_TEMPLATE_OUTPUT = 256 * 1024  # 256KiB


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

    from homeassistant.helpers.event import async_track_time_interval  # noqa: PLC0415

    cancel = async_track_time_interval(
        hass, _async_adjust_lru_sizes, timedelta(minutes=10)
    )
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_adjust_lru_sizes)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, callback(lambda _: cancel()))
    return True


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


class Template:
    """Class to hold a template and manage caching and rendering."""

    __slots__ = (
        "__weakref__",
        "_compiled",
        "_compiled_code",
        "_exc_info",
        "_hash_cache",
        "_limited",
        "_log_fn",
        "_renders",
        "_strict",
        "hass",
        "is_static",
        "template",
    )

    def __init__(self, template: str, hass: HomeAssistant) -> None:
        """Instantiate a template."""
        if not isinstance(template, str):
            raise TypeError("Expected template to be a string")

        self.template: str = template.strip()
        self._compiled_code: CodeType | None = None
        self._compiled: jinja2.Template | None = None
        self.hass = hass
        self.is_static = not is_template_string(template)
        self._exc_info: OptExcInfo | None = None
        self._limited: bool | None = None
        self._strict: bool | None = None
        self._log_fn: Callable[[int, str], None] | None = None
        self._hash_cache: int = hash(self.template)
        self._renders: int = 0

    @property
    def _env(self) -> TemplateEnvironment:
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

        with template_context_manager as cm:
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
            if not parse_result or (self.hass and self.hass.config.legacy_templates):
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
            if not parse_result or (self.hass and self.hass.config.legacy_templates):
                return self.template
            return self._parse_result(self.template)

        compiled = self._compiled or self._ensure_compiled(limited, strict, log_fn)

        if variables is not None:
            kwargs.update(variables)

        try:
            render_result = render_with_context(self.template, compiled, **kwargs)
        except Exception as err:
            raise TemplateError(err) from err

        if len(render_result) > MAX_TEMPLATE_OUTPUT:
            raise TemplateError(
                f"Template output exceeded maximum size of {MAX_TEMPLATE_OUTPUT} characters"
            )

        render_result = render_result.strip()

        if not parse_result or (self.hass and self.hass.config.legacy_templates):
            return render_result

        return self._parse_result(render_result)

    def _parse_result(self, render_result: str) -> Any:
        """Parse the result."""
        try:
            return _cached_parse_result(render_result)
        except ValueError, TypeError, SyntaxError, MemoryError:
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
                render_with_context(self.template, compiled, **kwargs)
            except TimeoutError:
                pass
            except Exception:  # noqa: BLE001
                self._exc_info = sys.exc_info()
            finally:
                self.hass.loop.call_soon_threadsafe(finish_event.set)

        template_render_thread = ThreadWithException(target=_render_template)
        try:
            template_render_thread.start()
            async with asyncio.timeout(timeout):
                await finish_event.wait()
            if self._exc_info:
                raise TemplateError(self._exc_info[1].with_traceback(self._exc_info[2]))
        except TimeoutError:
            if template_render_thread.is_alive():
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

        if render_info_cv.get() is not None:
            raise RuntimeError(
                f"RenderInfo already set while rendering {self}, "
                "this usually indicates the template is being rendered "
                "in the wrong thread"
            )

        if self.is_static:
            render_info._result = self.template.strip()  # noqa: SLF001
            render_info._freeze_static()  # noqa: SLF001
            return render_info

        token = render_info_cv.set(render_info)
        try:
            render_info._result = self.async_render(  # noqa: SLF001
                variables, strict=strict, log_fn=log_fn, **kwargs
            )
        except TemplateError as ex:
            render_info.exception = ex
        finally:
            render_info_cv.reset(token)

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
            render_result = render_with_context(
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

        if not parse_result or (self.hass and self.hass.config.legacy_templates):
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
        assert self._limited is None or self._limited == limited, (
            "can't change between limited and non limited template"
        )
        assert self._strict is None or self._strict == strict, (
            "can't change between strict and non strict template"
        )
        assert not (strict and limited), "can't combine strict and limited template"
        assert self._log_fn is None or self._log_fn == log_fn, (
            "can't change custom log function"
        )
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
        self.limited = limited
        self.template_cache: weakref.WeakValueDictionary[
            str | jinja2.nodes.Template, CodeType | None
        ] = weakref.WeakValueDictionary()
        self.add_extension("jinja2.ext.loopcontrols")
        self.add_extension("jinja2.ext.do")
        self.add_extension("homeassistant.helpers.template.extensions.AreaExtension")
        self.add_extension("homeassistant.helpers.template.extensions.Base64Extension")
        self.add_extension(
            "homeassistant.helpers.template.extensions.CollectionExtension"
        )
        self.add_extension(
            "homeassistant.helpers.template.extensions.ConfigEntryExtension"
        )
        self.add_extension("homeassistant.helpers.template.extensions.CryptoExtension")
        self.add_extension(
            "homeassistant.helpers.template.extensions.DateTimeExtension"
        )
        self.add_extension("homeassistant.helpers.template.extensions.DeviceExtension")
        self.add_extension("homeassistant.helpers.template.extensions.EntityExtension")
        self.add_extension("homeassistant.helpers.template.extensions.FloorExtension")
        self.add_extension(
            "homeassistant.helpers.template.extensions.FunctionalExtension"
        )
        self.add_extension("homeassistant.helpers.template.extensions.IssuesExtension")
        self.add_extension("homeassistant.helpers.template.extensions.LabelExtension")
        self.add_extension("homeassistant.helpers.template.extensions.MathExtension")
        self.add_extension("homeassistant.helpers.template.extensions.RegexExtension")
        self.add_extension(
            "homeassistant.helpers.template.extensions.SerializationExtension"
        )
        self.add_extension("homeassistant.helpers.template.extensions.StateExtension")
        self.add_extension("homeassistant.helpers.template.extensions.StringExtension")
        self.add_extension(
            "homeassistant.helpers.template.extensions.TypeCastExtension"
        )
        self.add_extension("homeassistant.helpers.template.extensions.VersionExtension")

        if hass is not None:
            # This environment has access to hass, attach its loader
            # to enable imports.
            self.loader = _get_hass_loader(hass)

    def is_safe_callable(self, obj):
        """Test if callback is safe."""
        return isinstance(
            obj, (AllStates, StateAttrTranslated, StateTranslated)
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
