"""Issues for InfluxDB integration."""

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

DEPRECATED_YAML_ISSUE_ID = f"deprecated_yaml_{DOMAIN}"


@callback
def deprecate_yaml_issue(hass: HomeAssistant) -> None:
    """Create a repair issue for deprecated YAML connection configuration."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        DEPRECATED_YAML_ISSUE_ID,
        is_fixable=False,
        issue_domain=DOMAIN,
        breaks_in_ha_version="2026.10.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "InfluxDB",
        },
    )


@callback
def import_connection_error_issue(hass: HomeAssistant, error: str) -> None:
    """Create a repair issue for a failed YAML import due to a connection error."""
    async_delete_issue(hass, HOMEASSISTANT_DOMAIN, DEPRECATED_YAML_ISSUE_ID)
    async_create_issue(
        hass,
        DOMAIN,
        "import_connection_error",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="import_connection_error",
        translation_placeholders={
            "error": error,
            "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
        },
    )
