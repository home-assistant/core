"""Logbook descriptions for ISEO Argo BLE Lock events."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, EVENT_TYPE


def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Any,
) -> None:
    """Register descriptions for custom events in the HA logbook."""

    @callback
    def _describe(event: Any) -> dict[str, str]:
        data = event.data
        message: str = data.get("message") or data.get("name") or "access event"
        return {
            "name": "ISEO Lock",
            "message": message,
        }

    async_describe_event(DOMAIN, EVENT_TYPE, _describe)
