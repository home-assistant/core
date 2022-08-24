"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude access_token and entity_picture from being recorded in the database."""
    return {"access_token", "entity_picture"}
