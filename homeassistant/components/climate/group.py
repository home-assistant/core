"""Describe group states."""

from typing import Callable

from homeassistant.const import STATE_OFF
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from .const import HVAC_MODE_OFF, HVAC_MODES


@callback
def async_describe_on_off_states(
    hass: HomeAssistantType, async_on_off_states: Callable
) -> None:
    """Describe group on off states."""
    async_on_off_states(
        set(HVAC_MODES) - {HVAC_MODE_OFF},
        STATE_OFF,
    )
