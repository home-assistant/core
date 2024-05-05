"""Issues for OpenWeatherMap."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def create_issue(hass: HomeAssistant):
    """Create issue for V2.5 deprecation."""
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id="deprecated_v25",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        learn_more_url="https://openweathermap.org/one-call-transfer",
        translation_key="deprecated_v25",
    )
