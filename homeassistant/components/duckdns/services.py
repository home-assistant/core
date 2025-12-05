"""Actions for Duck DNS."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import ATTR_CONFIG_ENTRY, ATTR_TXT, DOMAIN, SERVICE_SET_TXT
from .coordinator import DuckDnsConfigEntry
from .helpers import update_duckdns

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
        if len(entries := hass.config_entries.async_entries(DOMAIN)) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_selected",
            )
        return entries[0]
    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
        )
    return entry


async def update_domain_service(call: ServiceCall) -> None:
    """Update the DuckDNS entry."""

    entry = get_config_entry(call.hass, call.data.get(ATTR_CONFIG_ENTRY))

    session = async_get_clientsession(call.hass)

    await update_duckdns(
        session,
        entry.data[CONF_DOMAIN],
        entry.data[CONF_ACCESS_TOKEN],
        txt=call.data.get(ATTR_TXT),
    )
