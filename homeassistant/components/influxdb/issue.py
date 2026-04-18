"""Issues for InfluxDB integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


@callback
def async_create_deprecated_yaml_issue(
    hass: HomeAssistant, *, error: str | None = None
) -> None:
    """Create a repair issue for deprecated YAML connection configuration."""
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
        issue_domain=DOMAIN,
        breaks_in_ha_version="2026.9.0",
        severity=severity,
        translation_key=issue_id,
        translation_placeholders={
            "domain": DOMAIN,
            "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
        },
    )
