"""Repair issues for the HTTP integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN

# HTTP touches every installation, so we allow at least a full 12 months for
# users to migrate.
BREAKS_IN_HA_VERSION = "2027.6.0"


@callback
def async_create_deprecated_yaml_issue(hass: HomeAssistant) -> None:
    """Create a repair issue for deprecated YAML configuration."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN},
    )


@callback
def async_create_failed_to_start_issue(hass: HomeAssistant, *, error: str) -> None:
    """Surface that HTTP fell back to safe defaults during startup."""
    async_create_issue(
        hass,
        DOMAIN,
        "http_failed_to_start",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="http_failed_to_start",
        translation_placeholders={"error": error},
    )
