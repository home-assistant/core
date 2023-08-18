"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude description and location from being recorded in the database."""
    return {"description", "location"}
