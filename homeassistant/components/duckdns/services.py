"""Actions for Duck DNS."""

from enum import StrEnum

from aiohttp import ClientError
import probatio

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN, CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .helpers import update_duckdns


class DuckDnsService(StrEnum):
    """Store keys for Duck DNS services."""

    SET_TXT = "set_txt"


class DuckDnsServiceArgument(StrEnum):
    """Store keys for Duck DNS service arguments."""

    TXT = "txt"


SERVICE_TXT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Optional(DuckDnsServiceArgument.TXT): probatio.Any(None, cv.string),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Habitica integration."""

    hass.services.async_register(
        DOMAIN,
        DuckDnsService.SET_TXT,
        update_domain_service,
        schema=SERVICE_TXT_SCHEMA,
    )


async def update_domain_service(call: ServiceCall) -> None:
    """Update the DuckDNS entry."""

    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )

    session = async_get_clientsession(call.hass)

    try:
        if not await update_duckdns(
            session,
            entry.data[CONF_DOMAIN],
            entry.data[CONF_ACCESS_TOKEN],
            txt=call.data.get(DuckDnsServiceArgument.TXT),
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "domain": entry.data[CONF_DOMAIN],
                },
            )
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={
                "domain": entry.data[CONF_DOMAIN],
            },
        ) from e
