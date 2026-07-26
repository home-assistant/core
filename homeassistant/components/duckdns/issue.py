"""Issues for Duck DNS integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


def action_called_without_config_entry(hass: HomeAssistant) -> None:
    """Deprecate the use of action without config entry."""

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_call_without_config_entry",
        breaks_in_ha_version="2026.9.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_call_without_config_entry",
    )
