"""Services for the Fan integration."""

import probatio

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
    DATA_COMPONENT,
    SERVICE_DECREASE_SPEED,
    SERVICE_INCREASE_SPEED,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the fan services."""
    component = hass.data[DATA_COMPONENT]

    # After the transition to percentage and preset_modes concludes,
    # switch this back to async_turn_on and remove async_turn_on_compat
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            probatio.Optional(ATTR_PERCENTAGE): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            ),
            probatio.Optional(ATTR_PRESET_MODE): cv.string,
        },
        "async_handle_turn_on_service",
        [FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, None, "async_turn_off", [FanEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [FanEntityFeature.TURN_OFF, FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_INCREASE_SPEED,
        {
            probatio.Optional(ATTR_PERCENTAGE_STEP): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        "async_increase_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_DECREASE_SPEED,
        {
            probatio.Optional(ATTR_PERCENTAGE_STEP): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        "async_decrease_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_OSCILLATE,
        {probatio.Required(ATTR_OSCILLATING): cv.boolean},
        "async_oscillate",
        [FanEntityFeature.OSCILLATE],
    )
    component.async_register_entity_service(
        SERVICE_SET_DIRECTION,
        {probatio.Optional(ATTR_DIRECTION): cv.string},
        "async_set_direction",
        [FanEntityFeature.DIRECTION],
    )
    component.async_register_entity_service(
        SERVICE_SET_PERCENTAGE,
        {
            probatio.Required(ATTR_PERCENTAGE): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        "async_set_percentage",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {probatio.Required(ATTR_PRESET_MODE): cv.string},
        "async_handle_set_preset_mode_service",
        [FanEntityFeature.SET_SPEED, FanEntityFeature.PRESET_MODE],
    )
