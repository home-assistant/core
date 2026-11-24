"""Services for the counter integration."""

import probatio

from homeassistant.core import HomeAssistant, callback

from .const import DATA_COMPONENT, CounterService, CounterServiceArgument


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the counter services."""
    component = hass.data[DATA_COMPONENT]
    component.async_register_entity_service(
        CounterService.INCREMENT, None, "async_increment"
    )
    component.async_register_entity_service(
        CounterService.DECREMENT, None, "async_decrement"
    )
    component.async_register_entity_service(CounterService.RESET, None, "async_reset")
    component.async_register_entity_service(
        CounterService.SET_VALUE,
        {probatio.Required(CounterServiceArgument.VALUE): probatio.Coerce(int)},
        "async_set_value",
    )
