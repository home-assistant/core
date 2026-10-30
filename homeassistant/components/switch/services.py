"""Services for the Switch integration."""

from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT, SwitchService


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the switch services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SwitchService.TURN_OFF, None, "async_turn_off"
    )
    component.async_register_entity_service(
        SwitchService.TURN_ON, None, "async_turn_on"
    )
    component.async_register_entity_service(SwitchService.TOGGLE, None, "async_toggle")
