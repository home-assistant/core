"""Services for the Valve integration."""

import probatio

from homeassistant.const import (
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    SERVICE_TOGGLE,
)
from homeassistant.core import HomeAssistant, callback

from .const import ATTR_POSITION, DATA_COMPONENT, ValveEntityFeature


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the valve services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_OPEN_VALVE, None, "async_handle_open_valve", [ValveEntityFeature.OPEN]
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_VALVE,
        None,
        "async_handle_close_valve",
        [ValveEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_SET_VALVE_POSITION,
        {
            probatio.Required(ATTR_POSITION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        "async_set_valve_position",
        [ValveEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_STOP_VALVE, None, "async_stop_valve", [ValveEntityFeature.STOP]
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE],
    )
