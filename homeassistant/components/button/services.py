"""Services for the Button integration."""

from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT, ButtonService


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the button services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        ButtonService.PRESS,
        None,
        "_async_press_action",
    )
