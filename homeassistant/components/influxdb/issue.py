"""Issues for InfluxDB integration."""

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


@callback
def deprecate_yaml_issue(hass: HomeAssistant) -> None:
    """Create a repair issue for deprecated YAML connection configuration."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
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
def deprecated_yaml_import_issue_error(hass: HomeAssistant) -> None:
    """Create a repair issue for a failed YAML import."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_import_issue_error",
        breaks_in_ha_version="2026.10.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_issue_error",
        translation_placeholders={
            "url": "/config/integrations/dashboard/add?domain=influxdb",
        },
    )
