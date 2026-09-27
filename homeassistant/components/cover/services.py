"""Services for the Cover integration."""

import probatio

from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_POSITION,
    ATTR_SPEED,
    ATTR_TILT_POSITION,
    DATA_COMPONENT,
    CoverEntityFeature,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the cover services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_OPEN_COVER,
        {probatio.Optional(ATTR_SPEED): cv.string},
        "async_handle_open_cover",
        [CoverEntityFeature.OPEN],
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER,
        {probatio.Optional(ATTR_SPEED): cv.string},
        "async_handle_close_cover",
        [CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_POSITION,
        {
            probatio.Required(ATTR_POSITION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            ),
            probatio.Optional(ATTR_SPEED): cv.string,
        },
        "async_handle_set_cover_position",
        [CoverEntityFeature.SET_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER, None, "async_stop_cover", [CoverEntityFeature.STOP]
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE],
    )

    component.async_register_entity_service(
        SERVICE_OPEN_COVER_TILT,
        None,
        "async_open_cover_tilt",
        [CoverEntityFeature.OPEN_TILT],
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER_TILT,
        None,
        "async_close_cover_tilt",
        [CoverEntityFeature.CLOSE_TILT],
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER_TILT,
        None,
        "async_stop_cover_tilt",
        [CoverEntityFeature.STOP_TILT],
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_TILT_POSITION,
        {
            probatio.Required(ATTR_TILT_POSITION): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            )
        },
        "async_set_cover_tilt_position",
        [CoverEntityFeature.SET_TILT_POSITION],
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE_COVER_TILT,
        None,
        "async_toggle_tilt",
        [CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT],
    )
