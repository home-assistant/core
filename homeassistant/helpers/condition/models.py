"""Common condition classes and constants."""

import abc
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Never, TypedDict, Unpack, final

import probatio

from homeassistant.const import CONF_CONDITION, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trace import trace_path
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.util.hass_dict import HassKey

from .tracing import condition_trace_update_result, trace_condition

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
