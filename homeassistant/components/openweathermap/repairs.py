"""Issues for OpenWeatherMap."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def _get_issue_id(entry_id: str) -> str:
    return f"deprecated_v25_{entry_id}"


@callback
def async_create_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create issue for V2.5 deprecation."""
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=_get_issue_id(entry_id),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        learn_more_url="https://www.home-assistant.io/integrations/openweathermap/",
        translation_key="deprecated_v25",
    )


@callback
def async_delete_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Remove issue for V2.5 deprecation."""
    ir.async_delete_issue(hass=hass, domain=DOMAIN, issue_id=_get_issue_id(entry_id))
