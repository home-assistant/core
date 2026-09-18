"""Services for the Switch integration."""

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the switch services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")
