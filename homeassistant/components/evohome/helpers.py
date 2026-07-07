"""Helpers for the Evohome integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


@callback
def async_create_deprecation_issue_once(
    hass: HomeAssistant,
    issue_id: str,
    breaks_in_ha_version: str,
    translation_key: str | None = None,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Create or update a deprecation issue entry."""

    placeholders = {
        **(translation_placeholders or {}),
        "breaks_in_ha_version": breaks_in_ha_version,
    }

    ir.async_get(hass).async_get_or_create(
        DOMAIN,
        issue_id,
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key or issue_id,
        translation_placeholders=placeholders,
    )
