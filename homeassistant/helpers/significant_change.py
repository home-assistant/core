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
) -> Optional[bool]
```

Return boolean to indicate if significantly changed. If don't know, return None.

**kwargs will allow us to expand this feature in the future, like passing in a
level of significance.

The following cases will never be passed to your function:
- if either state is unknown/unavailable
- state adding/removing
"""
from types import MappingProxyType
from typing import Any, Callable, Dict, Optional, Union

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback

from .integration_platform import async_process_integration_platforms

PLATFORM = "significant_change"
DATA_FUNCTIONS = "significant_change"
CheckTypeFunc = Callable[
    [
        HomeAssistant,
        str,
        Union[dict, MappingProxyType],
        str,
        Union[dict, MappingProxyType],
    ],
    Optional[bool],
]


async def create_checker(
    hass: HomeAssistant, _domain: str
) -> "SignificantlyChangedChecker":
    """Create a significantly changed checker for a domain."""
    await _initialize(hass)
    return SignificantlyChangedChecker(hass)


# Marked as singleton so multiple calls all wait for same output.
async def _initialize(hass: HomeAssistant) -> None:
    """Initialize the functions."""
    if DATA_FUNCTIONS in hass.data:
        return

    functions = hass.data[DATA_FUNCTIONS] = {}

    async def process_platform(
        hass: HomeAssistant, component_name: str, platform: Any
    ) -> None:
        """Process a significant change platform."""
        functions[component_name] = platform.async_check_significant_change

    await async_process_integration_platforms(hass, PLATFORM, process_platform)


def either_one_none(val1: Optional[Any], val2: Optional[Any]) -> bool:
    """Test if exactly one value is None."""
    return (val1 is None and val2 is not None) or (val1 is not None and val2 is None)


def check_numeric_changed(
    val1: Optional[Union[int, float]],
    val2: Optional[Union[int, float]],
    change: Union[int, float],
) -> bool:
    """Check if two numeric values have changed."""
    if val1 is None and val2 is None:
        return False

    if either_one_none(val1, val2):
        return True

    assert val1 is not None
    assert val2 is not None

    if abs(val1 - val2) >= change:
        return True

    return False


class SignificantlyChangedChecker:
    """Class to keep track of entities to see if they have significantly changed.

    Will always compare the entity to the last entity that was considered significant.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Test if an entity has significantly changed."""
        self.hass = hass
        self.last_approved_entities: Dict[str, State] = {}

    @callback
    def async_is_significant_change(self, new_state: State) -> bool:
        """Return if this was a significant change."""
        old_state: Optional[State] = self.last_approved_entities.get(
            new_state.entity_id
        )

        # First state change is always ok to report
        if old_state is None:
            self.last_approved_entities[new_state.entity_id] = new_state
            return True

        # Handle state unknown or unavailable
        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            if new_state.state == old_state.state:
                return False

            self.last_approved_entities[new_state.entity_id] = new_state
            return True

        # If last state was unknown/unavailable, also significant.
        if old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self.last_approved_entities[new_state.entity_id] = new_state
            return True

        functions: Optional[Dict[str, CheckTypeFunc]] = self.hass.data.get(
            DATA_FUNCTIONS
        )

        if functions is None:
            raise RuntimeError("Significant Change not initialized")

        check_significantly_changed = functions.get(new_state.domain)

        # No platform available means always true.
        if check_significantly_changed is None:
            self.last_approved_entities[new_state.entity_id] = new_state
            return True

        result = check_significantly_changed(
            self.hass,
            old_state.state,
            old_state.attributes,
            new_state.state,
            new_state.attributes,
        )

        if result is False:
            return False

        # Result is either True or None.
        # None means the function doesn't know. For now assume it's True
        self.last_approved_entities[new_state.entity_id] = new_state
        return True
