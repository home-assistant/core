"""Services for the counter integration."""

import probatio

from homeassistant.core import HomeAssistant, callback

from .const import (
    DATA_COMPONENT,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_RESET,
    SERVICE_SET_VALUE,
    VALUE,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the counter services."""
    component = hass.data[DATA_COMPONENT]
    component.async_register_entity_service(SERVICE_INCREMENT, None, "async_increment")
    component.async_register_entity_service(SERVICE_DECREMENT, None, "async_decrement")
    component.async_register_entity_service(SERVICE_RESET, None, "async_reset")
    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {probatio.Required(VALUE): probatio.Coerce(int)},
        "async_set_value",
    )
