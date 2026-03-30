"""Actions for Duck DNS."""

from __future__ import annotations

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import ATTR_CONFIG_ENTRY, ATTR_TXT, DOMAIN, SERVICE_SET_TXT
from .coordinator import DuckDnsConfigEntry
from .helpers import update_duckdns
from .issue import action_called_without_config_entry

SERVICE_TXT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
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


def get_config_entry(
    hass: HomeAssistant, entry_id: str | None = None
) -> DuckDnsConfigEntry:
    """Return config entry or raise if not found or not loaded."""

    if entry_id is None:
        action_called_without_config_entry(hass)
        if len(entries := hass.config_entries.async_entries(DOMAIN)) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_selected",
            )
        entry_id = entries[0].entry_id

    return service.async_get_config_entry(hass, DOMAIN, entry_id)


async def update_domain_service(call: ServiceCall) -> None:
    """Update the DuckDNS entry."""

    entry = get_config_entry(call.hass, call.data.get(ATTR_CONFIG_ENTRY))

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
