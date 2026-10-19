"""Services for the Lawn mower integration."""

from homeassistant.core import HomeAssistant, callback

from .const import (
    DATA_COMPONENT,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    SERVICE_STOP,
    LawnMowerEntityFeature,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the lawn mower services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_START_MOWING,
        None,
        "async_start_mowing",
        [LawnMowerEntityFeature.START_MOWING],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE, None, "async_pause", [LawnMowerEntityFeature.PAUSE]
    )
    component.async_register_entity_service(
        SERVICE_DOCK, None, "async_dock", [LawnMowerEntityFeature.DOCK]
    )
    component.async_register_entity_service(
        SERVICE_STOP, None, "async_stop", [LawnMowerEntityFeature.STOP]
    )
