"""Support for KEBA charging station services."""

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN

_SERVICE_MAP = {
    "request_data": "async_request_data",
    "set_energy": "async_set_energy",
    "set_current": "async_set_current",
    "authorize": "async_start",
    "deauthorize": "async_stop",
    "enable": "async_enable_ev",
    "disable": "async_disable_ev",
    "set_failsafe": "async_set_failsafe",
}


async def _async_execute_service(call: ServiceCall) -> None:
    """Execute a service to KEBA charging station."""
    keba = call.hass.data[DOMAIN]
    function_call = getattr(keba, _SERVICE_MAP[call.service])
    await function_call(call.data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the KEBA services."""
    for service in _SERVICE_MAP:
        hass.services.async_register(DOMAIN, service, _async_execute_service)
