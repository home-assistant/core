"""Helper functions for the Home Assistant Labs integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.const import EVENT_LABS_UPDATED
from homeassistant.core import Event, HomeAssistant, callback

from .const import LABS_DATA
from .models import EventLabsUpdatedData


@callback
def async_is_preview_feature_enabled(
    hass: HomeAssistant, domain: str, preview_feature: str
) -> bool:
    """Check if a lab preview feature is enabled.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        preview_feature: Preview feature name

    Returns:
        True if the preview feature is enabled, False otherwise
    """
    if LABS_DATA not in hass.data:
        return False

    labs_data = hass.data[LABS_DATA]
    return (domain, preview_feature) in labs_data.data.preview_feature_status


@callback
def async_listen(
    hass: HomeAssistant,
    domain: str,
    preview_feature: str,
    listener: Callable[[], None],
) -> Callable[[], None]:
    """Listen for changes to a specific preview feature.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        preview_feature: Preview feature name
        listener: Callback to invoke when the preview feature is toggled

    Returns:
        Callable to unsubscribe from the listener
    """

    @callback
    def _async_feature_updated(event: Event[EventLabsUpdatedData]) -> None:
        """Handle labs feature update event."""
        if (
            event.data["domain"] == domain
            and event.data["preview_feature"] == preview_feature
        ):
            listener()

    return hass.bus.async_listen(EVENT_LABS_UPDATED, _async_feature_updated)
