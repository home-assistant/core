"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.counter import (
    DOMAIN,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_RESET,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass


@callback
@bind_hass
def async_increment(hass: HomeAssistant, entity_id: str) -> None:
    """Increment a counter."""
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_INCREMENT, {ATTR_ENTITY_ID: entity_id})
    )


@callback
@bind_hass
def async_decrement(hass: HomeAssistant, entity_id: str) -> None:
    """Decrement a counter."""
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_DECREMENT, {ATTR_ENTITY_ID: entity_id})
    )


@callback
@bind_hass
def async_reset(hass: HomeAssistant, entity_id: str) -> None:
    """Reset a counter."""
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_RESET, {ATTR_ENTITY_ID: entity_id})
    )
