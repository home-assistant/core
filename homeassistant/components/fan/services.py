"""Services for the Fan integration."""

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, FanEntityFeature, FanService, FanServiceArgument


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the fan services."""
    component = hass.data[DATA_COMPONENT]

    # After the transition to percentage and preset_modes concludes,
    # switch this back to async_turn_on and remove async_turn_on_compat
    component.async_register_entity_service(
        FanService.TURN_ON,
        {
            probatio.Optional(FanServiceArgument.PERCENTAGE): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            ),
            probatio.Optional(FanServiceArgument.PRESET_MODE): cv.string,
        },
        "async_handle_turn_on_service",
        [FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        FanService.TURN_OFF, None, "async_turn_off", [FanEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        FanService.TOGGLE,
        None,
        "async_toggle",
        [FanEntityFeature.TURN_OFF, FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        FanService.INCREASE_SPEED,
        {
            probatio.Optional(FanServiceArgument.PERCENTAGE_STEP): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        "async_increase_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        FanService.DECREASE_SPEED,
        {
            probatio.Optional(FanServiceArgument.PERCENTAGE_STEP): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        "async_decrease_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        FanService.OSCILLATE,
        {probatio.Required(FanServiceArgument.OSCILLATING): cv.boolean},
        "async_oscillate",
        [FanEntityFeature.OSCILLATE],
    )
    component.async_register_entity_service(
        FanService.SET_DIRECTION,
        {probatio.Optional(FanServiceArgument.DIRECTION): cv.string},
        "async_set_direction",
        [FanEntityFeature.DIRECTION],
    )
    component.async_register_entity_service(
        FanService.SET_PERCENTAGE,
        {
            probatio.Required(FanServiceArgument.PERCENTAGE): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        "async_set_percentage",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        FanService.SET_PRESET_MODE,
        {probatio.Required(FanServiceArgument.PRESET_MODE): cv.string},
        "async_handle_set_preset_mode_service",
        [FanEntityFeature.SET_SPEED, FanEntityFeature.PRESET_MODE],
    )
