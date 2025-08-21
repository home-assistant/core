"""The Volvo On Call integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Volvo On Call integration."""
    hass.data.setdefault(DOMAIN, {})

    # Create repair issue pointing to the new volvo integration
    ir.async_create_issue(
        hass,
        DOMAIN,
        "volvooncall_deprecated",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="volvooncall_deprecated",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ir.async_delete_issue(
        hass,
        DOMAIN,
        "volvooncall_deprecated",
    )

    return True
