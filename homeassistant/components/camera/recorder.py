"""Integration platform for recroder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude entity_picture and token from being recorded in the database."""
    return {"entity_picture", "token"}
