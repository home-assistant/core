"""Handles issues for the Prowl component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, YAML_DEPRECATED_IN


def async_create_prowl_yaml_issue(hass: HomeAssistant) -> None:
    """Create an issue for the Prowl integration."""
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=YAML_DEPRECATED_IN,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="prowl_yaml_deprecated",
    )
