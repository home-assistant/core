"""Support to control a Salda Smarty XP/XV ventilation unit."""

import ipaddress
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SmartyConfigEntry, SmartyCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
                vol.Optional(CONF_NAME, default="Smarty"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Create a smarty system."""
    if config := hass_config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, config))
    return True


async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the smarty environment."""

    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result["type"] == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result['reason']}",
                breaks_in_ha_version="2025.5.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Smarty",
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Smarty",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    """Set up the Smarty environment from a config entry."""

    coordinator = SmartyCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
