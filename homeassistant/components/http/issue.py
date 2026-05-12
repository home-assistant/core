"""Repair issues for the HTTP integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN

# Removing YAML support outright would lock out users mid-migration. HTTP
# touches every installation, so we allow a full release cycle (12 months) for
# users to migrate.
BREAKS_IN_HA_VERSION = "2027.6.0"


@callback
def async_create_deprecated_yaml_issue(
    hass: HomeAssistant, *, error: str | None = None
) -> None:
    """Create a repair issue for deprecated YAML configuration."""
    if error is None:
        issue_id = "deprecated_yaml"
        severity = IssueSeverity.WARNING
    else:
        issue_id = f"deprecated_yaml_import_issue_{error}"
        severity = IssueSeverity.ERROR

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        severity=severity,
        translation_key=issue_id,
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
