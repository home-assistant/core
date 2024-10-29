"""Utils for sql."""

from __future__ import annotations

import logging

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant

from .const import DB_URL_RE

_LOGGER = logging.getLogger(__name__)


def redact_credentials(data: str | None) -> str:
    """Redact credentials from string data."""
    if not data:
        return "none"
    return DB_URL_RE.sub("//****:****@", data)


def resolve_db_url(hass: HomeAssistant, db_url: str | None) -> str:
    """Return the db_url provided if not empty, otherwise return the recorder db_url."""
    _LOGGER.debug("db_url: %s", redact_credentials(db_url))
    if db_url and not db_url.isspace():
        return db_url
    return get_instance(hass).db_url
