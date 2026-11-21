"""Services for the Demo integration."""

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    SERVICE_RANDOMIZE_DEVICE_TRACKER_DATA,
    SIGNAL_RANDOMIZE_DEVICE_TRACKER_DATA,
)


@callback
def _async_randomize_device_tracker_data(call: ServiceCall) -> None:
    """Move the demo trackers to new random locations."""
    async_dispatcher_send(call.hass, SIGNAL_RANDOMIZE_DEVICE_TRACKER_DATA)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the demo actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RANDOMIZE_DEVICE_TRACKER_DATA,
        _async_randomize_device_tracker_data,
    )
