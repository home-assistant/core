"""Repair issue helpers for Besen BS20."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def async_create_no_connectable_path_issue(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    """Create an issue for missing active Bluetooth connectivity."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry_id}_no_connectable_path",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="no_connectable_path",
    )


def async_delete_no_connectable_path_issue(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    """Delete the missing active Bluetooth issue."""

    ir.async_delete_issue(hass, DOMAIN, f"{entry_id}_no_connectable_path")


def async_create_reauth_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create an issue for invalid charger PIN."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry_id}_reauth_required",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="reauth_required",
    )


def async_delete_reauth_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the invalid PIN repair issue."""

    ir.async_delete_issue(hass, DOMAIN, f"{entry_id}_reauth_required")

