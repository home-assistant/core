"""Helper functions for the Home Assistant Labs integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.const import EVENT_LABS_UPDATED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.frame import report_usage

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
def async_subscribe_preview_feature(
    hass: HomeAssistant,
    domain: str,
    preview_feature: str,
    listener: Callable[[EventLabsUpdatedData], Coroutine[Any, Any, None]],
) -> Callable[[], None]:
    """Listen for changes to a specific preview feature.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        preview_feature: Preview feature name
        listener: Coroutine function to invoke when the preview feature
            is toggled. Receives the event data as argument. Runs eagerly.

    Returns:
        Callable to unsubscribe from the listener
    """

    @callback
    def _async_event_filter(event_data: EventLabsUpdatedData) -> bool:
        """Filter labs events for this integration's preview feature."""
        return (
            event_data["domain"] == domain
            and event_data["preview_feature"] == preview_feature
        )

    async def _handler(event: Event[EventLabsUpdatedData]) -> None:
        """Handle labs feature update event."""
        await listener(event.data)

    return hass.bus.async_listen(
        EVENT_LABS_UPDATED, _handler, event_filter=_async_event_filter
    )


@callback
def async_listen(
    hass: HomeAssistant,
    domain: str,
    preview_feature: str,
    listener: Callable[[], None],
) -> Callable[[], None]:
    """Listen for changes to a specific preview feature.

    Deprecated: use async_subscribe_preview_feature instead.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        preview_feature: Preview feature name
        listener: Callback to invoke when the preview feature is toggled

    Returns:
        Callable to unsubscribe from the listener
    """
    report_usage(
        "calls `async_listen` which is deprecated, "
        "use `async_subscribe_preview_feature` instead",
        breaks_in_ha_version="2027.3.0",
    )

    async def _listener(_event_data: EventLabsUpdatedData) -> None:
        listener()

    return async_subscribe_preview_feature(hass, domain, preview_feature, _listener)


async def async_update_preview_feature(
    hass: HomeAssistant,
    domain: str,
    preview_feature: str,
    enabled: bool,
) -> None:
    """Update a lab preview feature state."""
    labs_data = hass.data[LABS_DATA]

    preview_feature_id = f"{domain}.{preview_feature}"

    if preview_feature_id not in labs_data.preview_features:
        raise ValueError(f"Preview feature {preview_feature_id} not found")

    if enabled:
        labs_data.data.preview_feature_status.add((domain, preview_feature))
    else:
        labs_data.data.preview_feature_status.discard((domain, preview_feature))

    await labs_data.store.async_save(labs_data.data.to_store_format())

    event_data: EventLabsUpdatedData = {
        "domain": domain,
        "preview_feature": preview_feature,
        "enabled": enabled,
    }
    hass.bus.async_fire(EVENT_LABS_UPDATED, event_data)
