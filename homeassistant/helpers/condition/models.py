"""Common condition classes and constants."""

import abc
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Never, TypedDict, Unpack, final, override

import probatio

from homeassistant.const import CONF_CONDITION, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trace import (
    TraceElement,
    trace_append_element,
    trace_path,
    trace_path_get,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

CONDITIONS: HassKey[dict[str, str]] = HassKey("conditions")


CONDITION_BASE_SCHEMA = probatio.Schema(
    {
        **cv.CONDITION_BASE_SCHEMA,
        probatio.Required(CONF_CONDITION): str,
    }
)
_CONDITION_SCHEMA = CONDITION_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_OPTIONS): object,
        probatio.Optional(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


@dataclass(slots=True)
class ConditionConfig:
    """Condition config."""

    options: dict[str, Any] | None = None
    target: dict[str, Any] | None = None


class ConditionCheckParams(TypedDict, total=False):
    """Condition check params."""

    variables: TemplateVarsType


type ConditionCheckerType = Callable[[HomeAssistant, TemplateVarsType], bool]
type ConditionCheckerTypeOptional = Callable[
    [HomeAssistant, TemplateVarsType], bool | None
]


class ConditionChecker(abc.ABC):
    """Base class for condition checkers."""

    _set_up = False
    _unloaded = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize condition checker."""
        self._hass = hass

    def __call__(
        self, hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool | None:
        """Check the condition.

        `hass` parameter is for backwards compatibility only and is always ignored.
        """
        return self.async_check(variables=variables)

    def __del__(self) -> None:
        """Clean up when the checker is deleted."""
        if self._unloaded:
            return
        try:
            self.async_unload()
        except Exception:
            _LOGGER.exception("Error while unloading condition checker")

    @final
    async def async_setup(self) -> None:
        """Set up the condition checker.

        Users of conditions do not need to call this method directly. It is called
        automatically by async_from_config and async_conditions_from_config.
        """
        await self._async_setup()
        self._set_up = True

    async def _async_setup(self) -> None:  # noqa: B027
        """Set up the condition checker.

        Intended to be overridden in derived classes that need to do setup.
        """

    @final
    def async_unload(self) -> None:
        """Clean up any resources held by the checker.

        Users of conditions must call this method when they are done with the
        checker to ensure resources are released.
        """
        self._async_unload()
        self._unloaded = True

    def _async_unload(self) -> None:  # noqa: B027
        """Clean up any resources held by the checker.

        Intended to be overridden in derived classes that need to do unloading.
        """

    @final
    def async_check(
        self, *, variables: TemplateVarsType = None, **kwargs: Never
    ) -> bool | None:
        """Check the condition."""
        if not self._set_up:
            raise HomeAssistantError("Condition checker is not set up")
        with trace_condition(variables):
            result = self._async_check(variables=variables)
            condition_trace_update_result(result=result)
            return result

    @abc.abstractmethod
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool | None:
        """Check the condition."""


class LegacyConditionChecker(ConditionChecker):
    """Condition checker wrapping a legacy condition factory function."""

    def __init__(self, hass: HomeAssistant, checker: ConditionCheckerType) -> None:
        """Initialize condition checker."""
        super().__init__(hass)
        self._checker = checker

    @override
    def _async_check(self, variables: TemplateVarsType = None, **kwargs: Any) -> bool:
        return self._checker(self._hass, variables)


class DisabledConditionChecker(ConditionChecker):
    """Condition checker for disabled conditions."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> None:
        return None


class CompoundConditionChecker(ConditionChecker):
    """Base class for compound condition checkers (and/or/not)."""

    def __init__(self, hass: HomeAssistant, conditions: list[ConditionChecker]) -> None:
        """Initialize condition checker."""
        super().__init__(hass)
        self._conditions = conditions

    @override
    def _async_unload(self) -> None:
        """Clean up child conditions."""
        for condition in self._conditions:
            condition.async_unload()


class AndConditionChecker(CompoundConditionChecker):
    """Condition checker for 'and' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test and condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "and", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was false
        if errors:
            raise ConditionErrorContainer("and", errors=errors)

        return True


class NotConditionChecker(CompoundConditionChecker):
    """Condition checker for 'not' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test not condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs):
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "not", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("not", errors=errors)

        return True


class OrConditionChecker(CompoundConditionChecker):
    """Condition checker for 'or' compound conditions."""

    @callback
    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test or condition."""
        errors = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["conditions", str(index)]):
                    if condition.async_check(**kwargs) is True:
                        return True
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "or", index=index, total=len(self._conditions), error=ex
                    )
                )

        # Raise the errors if no check was true
        if errors:
            raise ConditionErrorContainer("or", errors=errors)

        return False


class ConditionsChecker:
    """Condition checker that ANDs multiple conditions.

    Used by automations and template entities. Unlike AndConditionChecker,
    this logs warnings on errors instead of raising, and uses "condition"
    as the trace path prefix.
    """

    def __init__(
        self,
        conditions: list[ConditionChecker],
        logger: logging.Logger,
        name: str,
    ) -> None:
        """Initialize condition checker."""
        self._conditions = conditions
        self._logger = logger
        self._name = name
        self._unloaded = False

    def __call__(self, variables: TemplateVarsType = None) -> bool:
        """Check all conditions."""
        return self.async_check(variables=variables)

    def __del__(self) -> None:
        """Clean up when the checker is deleted."""
        if self._unloaded:
            return
        try:
            self.async_unload()
        except Exception:
            _LOGGER.exception("Error while unloading condition checker")

    def async_unload(self) -> None:
        """Clean up child conditions."""
        self._unloaded = True
        for condition in self._conditions:
            condition.async_unload()

    def async_check(
        self, *, variables: TemplateVarsType = None, **kwargs: Never
    ) -> bool:
        """AND all conditions."""
        errors: list[ConditionErrorIndex] = []
        for index, condition in enumerate(self._conditions):
            try:
                with trace_path(["condition", str(index)]):
                    if condition.async_check(variables=variables, **kwargs) is False:
                        return False
            except ConditionError as ex:
                errors.append(
                    ConditionErrorIndex(
                        "condition", index=index, total=len(self._conditions), error=ex
                    )
                )

        if errors:
            self._logger.warning(
                "Error evaluating condition in '%s':\n%s",
                self._name,
                ConditionErrorContainer("condition", errors=errors),
            )
            return False

        return True


class Condition(ConditionChecker):
    """Condition class."""

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config.

        The complete config includes fields that are generic to all conditions,
        such as the alias.
        This method should be overridden by conditions that need to migrate
        from the old-style config.
        """
        complete_config = _CONDITION_SCHEMA(complete_config)

        specific_config: ConfigType = {}
        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in complete_config:
                specific_config[key] = complete_config.pop(key)
        specific_config = await cls.async_validate_config(hass, specific_config)

        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in specific_config:
                complete_config[key] = specific_config[key]

        return complete_config

    @classmethod
    @abc.abstractmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass)


class trace_condition:
    """Trace condition evaluation."""

    __slots__ = ("_should_pop", "_trace_element", "_variables")

    _should_pop: bool
    _trace_element: TraceElement

    def __init__(self, variables: TemplateVarsType) -> None:
        """Store the variables for the trace element."""
        self._variables = variables

    def __enter__(self) -> TraceElement:
        """Start tracing the condition evaluation."""
        should_pop = True
        trace_element = trace_stack_top(trace_stack_cv)
        if trace_element and trace_element.reuse_by_child:
            should_pop = False
            trace_element.reuse_by_child = False
        else:
            trace_element = condition_trace_append(self._variables, trace_path_get())
            trace_stack_push(trace_stack_cv, trace_element)
        self._should_pop = should_pop
        self._trace_element = trace_element
        return trace_element

    def __exit__(
        self, exc_type: object, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Finish tracing the condition evaluation."""
        try:
            if exc_val is not None and isinstance(exc_val, Exception):
                self._trace_element.set_error(exc_val)
        finally:
            if self._should_pop:
                trace_stack_pop(trace_stack_cv)


def condition_trace_append(variables: TemplateVarsType, path: str) -> TraceElement:
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element)
    return trace_element


def condition_trace_set_result(result: bool, **kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.set_result(result=result, **kwargs)


def condition_trace_update_result(**kwargs: Any) -> None:
    """Update the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.update_result(**kwargs)
