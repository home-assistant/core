"""Support for Ambiclimate devices."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Ambiclimate components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass, conf[CONF_CLIENT_ID], conf[CONF_CLIENT_SECRET]
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ambiclimate from a config entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        breaks_in_ha_version="2024.4.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="integration_removed",
        translation_placeholders={
            "entries": "/config/integrations/integration/ambiclimate",
        },
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
