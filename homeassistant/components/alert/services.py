"""Services for the Alert integration."""

from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT, AlertService


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Alert integration."""
    component = hass.data[DATA_COMPONENT]
    component.async_register_entity_service(
        AlertService.TURN_OFF, None, "async_turn_off"
    )
    component.async_register_entity_service(AlertService.TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(AlertService.TOGGLE, None, "async_toggle")
