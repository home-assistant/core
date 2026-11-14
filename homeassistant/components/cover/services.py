"""Services for the Cover integration."""

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    CoverEntityFeature,
    CoverService,
    CoverServiceArgument,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the cover services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        CoverService.OPEN,
        {probatio.Optional(CoverServiceArgument.SPEED): cv.string},
        "async_handle_open_cover",
        [CoverEntityFeature.OPEN],
    )

    component.async_register_entity_service(
        CoverService.CLOSE,
        {probatio.Optional(CoverServiceArgument.SPEED): cv.string},
        "async_handle_close_cover",
        [CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        CoverService.SET_POSITION,
        {
            probatio.Required(CoverServiceArgument.POSITION): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            ),
            probatio.Optional(CoverServiceArgument.SPEED): cv.string,
        },
        "async_handle_set_cover_position",
        [CoverEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        CoverService.STOP, None, "async_stop_cover", [CoverEntityFeature.STOP]
    )

    component.async_register_entity_service(
        CoverService.TOGGLE,
        None,
        "async_toggle",
        [CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        CoverService.OPEN_TILT,
        None,
        "async_open_cover_tilt",
        [CoverEntityFeature.OPEN_TILT],
    )

    component.async_register_entity_service(
        CoverService.CLOSE_TILT,
        None,
        "async_close_cover_tilt",
        [CoverEntityFeature.CLOSE_TILT],
    )

    component.async_register_entity_service(
        CoverService.STOP_TILT,
        None,
        "async_stop_cover_tilt",
        [CoverEntityFeature.STOP_TILT],
    )

    component.async_register_entity_service(
        CoverService.SET_TILT_POSITION,
        {
            probatio.Required(CoverServiceArgument.TILT_POSITION): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            )
        },
        "async_set_cover_tilt_position",
        [CoverEntityFeature.SET_TILT_POSITION],
    )

    component.async_register_entity_service(
        CoverService.TOGGLE_TILT,
        None,
        "async_toggle_tilt",
        [CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT],
    )
