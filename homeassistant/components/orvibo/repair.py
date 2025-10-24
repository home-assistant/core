"""Repairs for Orvibo Integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

DOMAIN = "orvibo"


async def async_create_yaml_deprecation_issue(
    hass: HomeAssistant,
    host: str,
    mac: str,
    name: str,
) -> None:
    """Create a repair issue suggesting removal of YAML config."""
    async_create_issue(
        hass,
        DOMAIN,
        f"yaml_deprecation_{mac.replace(':', '').lower()}",
        is_fixable=False,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="yaml_deprecation",
        translation_placeholders={
            "host": host,
            "mac": mac,
            "name": name,
        },
    )
