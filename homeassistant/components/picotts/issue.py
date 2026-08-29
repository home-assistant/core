"""Issues for Pico TTS integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


@callback
def deprecate_yaml_issue(hass: HomeAssistant) -> None:
    """Deprecate yaml issue."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        breaks_in_ha_version="2026.10.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Pico TTS",
        },
    )
