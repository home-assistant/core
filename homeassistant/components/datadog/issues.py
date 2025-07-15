"""Issues for Datadog integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


async def deprecate_yaml_issue(
    hass: HomeAssistant,
    import_success: bool,
) -> None:
    """Create an issue to deprecate YAML config."""
    if import_success:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2026.2.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_connection_error",
            breaks_in_ha_version="2026.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_connection_error",
            translation_placeholders={
                "domain": DOMAIN,
                "url": "/config/integrations/dashboard/add?domain=datadog",
            },
        )
