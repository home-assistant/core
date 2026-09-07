"""Actions for Duck DNS."""

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import ATTR_CONFIG_ENTRY, ATTR_TXT, DOMAIN, SERVICE_SET_TXT
from .helpers import update_duckdns

SERVICE_TXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_TXT): vol.Any(None, cv.string),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Habitica integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TXT,
        update_domain_service,
        schema=SERVICE_TXT_SCHEMA,
    )


async def update_domain_service(call: ServiceCall) -> None:
    """Update the DuckDNS entry."""

    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
    )

    session = async_get_clientsession(call.hass)

    try:
        if not await update_duckdns(
            session,
            entry.data[CONF_DOMAIN],
            entry.data[CONF_ACCESS_TOKEN],
            txt=call.data.get(ATTR_TXT),
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    CONF_DOMAIN: entry.data[CONF_DOMAIN],
                },
            )
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={
                CONF_DOMAIN: entry.data[CONF_DOMAIN],
            },
        ) from e
