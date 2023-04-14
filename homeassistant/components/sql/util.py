"""Utils for sql."""
from __future__ import annotations

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant


def resolve_db_url(hass: HomeAssistant, db_url: str | None) -> str:
    """Return the db_url provided if not empty, otherwise return the recorder db_url."""
    if db_url and not db_url.isspace():
        return db_url
    return get_instance(hass).db_url
