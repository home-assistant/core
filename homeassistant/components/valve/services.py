"""Services for the Valve integration."""

import probatio

from homeassistant.core import HomeAssistant, callback

from .const import (
    DATA_COMPONENT,
    ValveEntityFeature,
    ValveService,
    ValveServiceArgument,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the valve services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        ValveService.OPEN,
        None,
        "async_handle_open_valve",
        [ValveEntityFeature.OPEN],
    )

    component.async_register_entity_service(
        ValveService.CLOSE,
        None,
        "async_handle_close_valve",
        [ValveEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        ValveService.SET_POSITION,
        {
            probatio.Required(ValveServiceArgument.POSITION): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        "async_set_valve_position",
        [ValveEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        ValveService.STOP, None, "async_stop_valve", [ValveEntityFeature.STOP]
    )

    component.async_register_entity_service(
        ValveService.TOGGLE,
        None,
        "async_toggle",
        [ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE],
    )
