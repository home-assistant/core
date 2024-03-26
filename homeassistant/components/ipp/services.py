"""IPP integration services."""

from __future__ import annotations

from base64 import b64encode
from functools import partial

from pyipp import IPP
from pyipp.enums import IppOperation
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    DOMAIN,
    SERVICE_IPP_ATTR_OPERATION,
    SERVICE_IPP_ATTR_PAYLOAD,
    SERVICE_IPP_DUMP,
)

SERVICE_IPP_DUMP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=631): int,
        vol.Optional(CONF_BASE_PATH, default="/ipp/print"): str,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        vol.Required(SERVICE_IPP_ATTR_OPERATION): cv.enum(IppOperation),
        vol.Required(SERVICE_IPP_ATTR_PAYLOAD): dict,
    }
)


@callback
def register_ipp_services(hass: HomeAssistant) -> None:
    """Register IPP integration services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_IPP_DUMP,
        partial(service_dump, hass),
        schema=SERVICE_IPP_DUMP_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def service_dump(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Send a request to the printer and dump its response."""
    ipp = IPP(
        host=call.data[CONF_HOST],
        port=call.data[CONF_PORT],
        base_path=call.data[CONF_BASE_PATH],
        tls=call.data[CONF_SSL],
        verify_ssl=call.data[CONF_VERIFY_SSL],
        session=async_get_clientsession(hass, call.data[CONF_VERIFY_SSL]),
    )

    operation = call.data[SERVICE_IPP_ATTR_OPERATION]
    payload = call.data[SERVICE_IPP_ATTR_PAYLOAD]
    response = await ipp.raw(operation, payload)

    return {
        "operation": operation.name,
        "payload": payload,
        "response": b64encode(response).decode("ascii"),
    }
