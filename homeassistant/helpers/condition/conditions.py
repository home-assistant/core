"""Common condition classes and constants."""

from typing import Any, Unpack, override

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConditionError,
    ConditionErrorContainer,
    ConditionErrorIndex,
)
from homeassistant.helpers.trace import trace_path
from homeassistant.helpers.typing import TemplateVarsType

from .models import ConditionChecker, ConditionCheckerType, ConditionCheckParams


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
