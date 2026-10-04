"""Issues for Prowl integration."""

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def async_create_yaml_deprecated_issue(hass: HomeAssistant) -> None:
    """Create an issue for the deprecated YAML configuration."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "Prowl"},
    )


@callback
def async_create_import_error_issue(
    hass: HomeAssistant, name: str | None, reason: str
) -> None:
    """Create an issue for a YAML configuration that could not be imported."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{slugify(name or DOMAIN)}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{reason}",
        translation_placeholders={
            "url": f"/config/integrations/dashboard/add?domain={DOMAIN}"
        },
    )
