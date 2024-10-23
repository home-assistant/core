"""The Niko home control integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS: list[str] = ["light"]

# delete after 2025.5.0
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


# delete after 2025.5.0
async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Create a smarty system."""
    if config := hass_config.get(DOMAIN):
        hass.async_create_task(_async_import(hass, config))
    return True


# delete after 2025.5.0
async def _async_import(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the smarty environment."""

    if not hass.config_entries.async_entries(DOMAIN):
        # Start import flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result.get("type") == FlowResultType.ABORT:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result.get('reason', 'unknown')}",
                breaks_in_ha_version="2025.5.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result.get('reason', 'unknown')}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Niko Home Control",
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
            "integration_title": "Niko Home Control",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set Niko Home Control from a config entry."""
    config = entry.data["config"]
    options = entry.data["options"]
    enabled_entities = entry.data["entities"]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "config": config,
        "enabled_entities": enabled_entities,
        "options": options,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
