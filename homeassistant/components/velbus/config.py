"""Velbus integration configuration helpers."""

from homeassistant.exceptions import ServiceValidationError

from .const import CONF_ADVANCED_MODE, DOMAIN
from .data import VelbusConfigEntry


def is_advanced_mode_enabled(entry: VelbusConfigEntry) -> bool:
    """Return whether advanced mode is enabled for the config entry."""
    return bool(entry.data.get(CONF_ADVANCED_MODE, False))


def require_advanced_mode(entry: VelbusConfigEntry) -> None:
    """Raise if advanced mode is not enabled."""
    if not is_advanced_mode_enabled(entry):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="advanced_mode_required",
        )
