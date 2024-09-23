"""Support for The Things network."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_APP_ID, DOMAIN, PLATFORMS, TTN_API_HOST
from .coordinator import TTNCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        # Configuration via yaml not longer supported - keeping to warn about migration
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_APP_ID): cv.string,
                vol.Required("access_key"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize of The Things Network component."""

    if DOMAIN in config:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "manual_migration",
            breaks_in_ha_version="2024.12.0",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="manual_migration",
            translation_placeholders={
                "domain": DOMAIN,
                "v2_v3_migration_url": "https://www.thethingsnetwork.org/forum/c/v2-to-v3-upgrade/102",
                "v2_deprecation_url": "https://www.thethingsnetwork.org/forum/t/the-things-network-v2-is-permanently-shutting-down-completed/50710",
            },
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with The Things Network."""

    _LOGGER.debug(
        "Set up %s at %s",
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_HOST, TTN_API_HOST),
    )

    coordinator = TTNCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug(
        "Remove %s at %s",
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_HOST, TTN_API_HOST),
    )

    # Unload entities created for each supported platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return True
