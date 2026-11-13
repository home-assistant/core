"""Support for KEBA charging station services."""

from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import DOMAIN, KebaService

_SERVICE_MAP: dict[str, str] = {
    KebaService.REQUEST_DATA: "async_request_data",
    KebaService.SET_ENERGY: "async_set_energy",
    KebaService.SET_CURRENT: "async_set_current",
    KebaService.AUTHORIZE: "async_start",
    KebaService.DEAUTHORIZE: "async_stop",
    KebaService.ENABLE: "async_enable_ev",
    KebaService.DISABLE: "async_disable_ev",
    KebaService.SET_FAILSAFE: "async_set_failsafe",
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
