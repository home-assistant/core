"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.counter import DOMAIN, CounterService
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant, callback


@callback
def async_increment(hass: HomeAssistant, entity_id: str) -> None:
    """Increment a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.INCREMENT, {TargetKey.ENTITY_ID: entity_id}
        )
    )


@callback
def async_decrement(hass: HomeAssistant, entity_id: str) -> None:
    """Decrement a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.DECREMENT, {TargetKey.ENTITY_ID: entity_id}
        )
    )


@callback
def async_reset(hass: HomeAssistant, entity_id: str) -> None:
    """Reset a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.RESET, {TargetKey.ENTITY_ID: entity_id}
        )
    )
