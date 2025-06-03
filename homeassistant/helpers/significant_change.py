"""Helpers to help find if an entity has changed significantly.

Does this with help of the integration. Looks at significant_change.py
platform for a function `async_check_significant_change`:

```python
from typing import Optional
from homeassistant.core import HomeAssistant

async def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs,
) -> bool | None
```

Return boolean to indicate if significantly changed. If don't know, return None.

**kwargs will allow us to expand this feature in the future, like passing in a
level of significance.

The following cases will never be passed to your function:
- if either state is unknown/unavailable
- state adding/removing
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, Protocol

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.util.hass_dict import HassKey

from .integration_platform import async_process_integration_platforms

PLATFORM = "significant_change"
DATA_FUNCTIONS: HassKey[dict[str, CheckTypeFunc]] = HassKey("significant_change")
type CheckTypeFunc = Callable[
    [
        HomeAssistant,
        str,
        dict | MappingProxyType,
        str,
        dict | MappingProxyType,
    ],
    bool | None,
]

type ExtraCheckTypeFunc = Callable[
    [
        HomeAssistant,
        str,
        dict | MappingProxyType,
        Any,
        str,
        dict | MappingProxyType,
        Any,
    ],
    bool | None,
]


class SignificantChangeProtocol(Protocol):
    """Define the format of significant_change platforms."""

    def async_check_significant_change(
        self,
        hass: HomeAssistant,
        old_state: str,
        old_attrs: Mapping[str, Any],
        new_state: str,
        new_attrs: Mapping[str, Any],
    ) -> bool | None:
        """Test if state significantly changed."""


async def create_checker(
    hass: HomeAssistant,
    _domain: str,
    extra_significant_check: ExtraCheckTypeFunc | None = None,
) -> SignificantlyChangedChecker:
    """Create a significantly changed checker for a domain."""
    await _initialize(hass)
    return SignificantlyChangedChecker(hass, extra_significant_check)


# Marked as singleton so multiple calls all wait for same output.
async def _initialize(hass: HomeAssistant) -> None:
    """Initialize the functions."""
    if DATA_FUNCTIONS in hass.data:
        return

    functions = hass.data[DATA_FUNCTIONS] = {}

    @callback
    def process_platform(
        hass: HomeAssistant,
        component_name: str,
        platform: SignificantChangeProtocol,
    ) -> None:
        """Process a significant change platform."""
        functions[component_name] = platform.async_check_significant_change

    await async_process_integration_platforms(hass, PLATFORM, process_platform)


def either_one_none(val1: Any | None, val2: Any | None) -> bool:
    """Test if exactly one value is None."""
    return (val1 is None and val2 is not None) or (val1 is not None and val2 is None)


def _check_numeric_change(
    old_state: float | None,
    new_state: float | None,
    change: float,
    metric: Callable[[int | float, int | float], int | float],
) -> bool:
    """Check if two numeric values have changed."""
    if old_state is None and new_state is None:
        return False

    if either_one_none(old_state, new_state):
        return True

    assert old_state is not None
    assert new_state is not None

    if metric(old_state, new_state) >= change:
        return True

    return False


def check_absolute_change(
    val1: float | None,
    val2: float | None,
    change: float,
) -> bool:
    """Check if two numeric values have changed."""
    return _check_numeric_change(
        val1, val2, change, lambda val1, val2: abs(val1 - val2)
    )


def check_percentage_change(
    old_state: float | None,
    new_state: float | None,
    change: float,
) -> bool:
    """Check if two numeric values have changed."""

    def percentage_change(old_state: float, new_state: float) -> float:
        if old_state == new_state:
            return 0
        try:
            return (abs(new_state - old_state) / old_state) * 100.0
        except ZeroDivisionError:
            return float("inf")

    return _check_numeric_change(old_state, new_state, change, percentage_change)


def check_valid_float(value: str | float) -> bool:
    """Check if given value is a valid float."""
    try:
        float(value)
    except ValueError:
        return False
    return True


class SignificantlyChangedChecker:
    """Class to keep track of entities to see if they have significantly changed.

    Will always compare the entity to the last entity that was considered significant.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        extra_significant_check: ExtraCheckTypeFunc | None = None,
    ) -> None:
        """Test if an entity has significantly changed."""
        self.hass = hass
        self.last_approved_entities: dict[str, tuple[State, Any]] = {}
        self.extra_significant_check = extra_significant_check

    @callback
    def async_is_significant_change(
        self, new_state: State, *, extra_arg: Any | None = None
    ) -> bool:
        """Return if this was a significant change.

        Extra kwargs are passed to the extra significant checker.
        """
        old_data: tuple[State, Any] | None = self.last_approved_entities.get(
            new_state.entity_id
        )

        # First state change is always ok to report
        if old_data is None:
            self.last_approved_entities[new_state.entity_id] = (new_state, extra_arg)
            return True

        old_state, old_extra_arg = old_data

        # Handle state unknown or unavailable
        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            if new_state.state == old_state.state:
                return False

            self.last_approved_entities[new_state.entity_id] = (new_state, extra_arg)
            return True

        # If last state was unknown/unavailable, also significant.
        if old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self.last_approved_entities[new_state.entity_id] = (new_state, extra_arg)
            return True

        functions = self.hass.data.get(DATA_FUNCTIONS)

        if functions is None:
            raise RuntimeError("Significant Change not initialized")

        check_significantly_changed = functions.get(new_state.domain)

        if check_significantly_changed is not None:
            result = check_significantly_changed(
                self.hass,
                old_state.state,
                old_state.attributes,
                new_state.state,
                new_state.attributes,
            )

            if result is False:
                return False

        if self.extra_significant_check is not None:
            result = self.extra_significant_check(
                self.hass,
                old_state.state,
                old_state.attributes,
                old_extra_arg,
                new_state.state,
                new_state.attributes,
                extra_arg,
            )

            if result is False:
                return False

        # Result is either True or None.
        # None means the function doesn't know. For now assume it's True
        self.last_approved_entities[new_state.entity_id] = (
            new_state,
            extra_arg,
        )
        return True
