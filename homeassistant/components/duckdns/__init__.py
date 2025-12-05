"""Integrate with DuckDNS."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_CONFIG_ENTRY
from .coordinator import DuckDnsConfigEntry, DuckDnsUpdateCoordinator
from .helpers import update_duckdns

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = "txt"

DOMAIN = "duckdns"

SERVICE_SET_TXT = "set_txt"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_TXT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Optional(ATTR_TXT): vol.Any(None, cv.string),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the DuckDNS component."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TXT,
        update_domain_service,
        schema=SERVICE_TXT_SCHEMA,
    )

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Set up Duck DNS from a config entry."""

    coordinator = DuckDnsUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Add a dummy listener as we do not have regular entities
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))

    return True


def get_config_entry(
    hass: HomeAssistant, entry_id: str | None = None
) -> DuckDnsConfigEntry:
    """Return config entry or raise if not found or not loaded."""

    if entry_id is None:
        if not (config_entries := hass.config_entries.async_entries(DOMAIN)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )

        if len(config_entries) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_selected",
            )
        return config_entries[0]

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


async def async_unload_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return True
