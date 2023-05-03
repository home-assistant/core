"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from .const import ATTR_EVENT_ID, ATTR_EVENT_SCORE


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude event_id and event_score from being recorded in the database."""
    return {ATTR_EVENT_ID, ATTR_EVENT_SCORE}
