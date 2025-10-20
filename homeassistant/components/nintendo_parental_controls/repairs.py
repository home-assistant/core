"""Implementations for repairs."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def raise_no_devices_found(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Create an issue if no devices are found."""
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id="no_devices_found",
        is_persistent=True,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="no_devices_found",
        translation_placeholders={"account_id": config_entry.title},
    )
