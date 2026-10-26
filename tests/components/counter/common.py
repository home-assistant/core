"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.counter import DOMAIN, CounterService
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback


@callback
def async_increment(hass: HomeAssistant, entity_id: str) -> None:
    """Increment a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.INCREMENT, {ATTR_ENTITY_ID: entity_id}
        )
    )


@callback
def async_decrement(hass: HomeAssistant, entity_id: str) -> None:
    """Decrement a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.DECREMENT, {ATTR_ENTITY_ID: entity_id}
        )
    )


@callback
def async_reset(hass: HomeAssistant, entity_id: str) -> None:
    """Reset a counter."""
    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, CounterService.RESET, {ATTR_ENTITY_ID: entity_id}
        )
    )
