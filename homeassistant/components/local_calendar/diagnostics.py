"""Provides diagnostics for local calendar."""

from collections.abc import Generator
import datetime
import itertools
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN

COMPONENT_ALLOWLIST = {
    "BEGIN",
    "END",
    "DTSTAMP",
    "CREATED",
    "LAST-MODIFIED",
    "DTSTART",
    "DTEND",
    "RRULE",
    "PRODID",
}
REDACT = "***"
MAX_CONTENTLINES = 5000


def redact_contentline(contentline: str) -> str:
    """Return a redacted version of an ics calendar."""
    if ":" in contentline:
        (component, _) = contentline.split(":", maxsplit=2)
        if component in COMPONENT_ALLOWLIST:
            return contentline
        return f"{component}:{REDACT}"
    return REDACT


def redact_ics(ics: str) -> Generator[str, None, None]:
    """Generate redacted ics file contents one line at a time."""
    contentlines = ics.split("\n")
    for contentline in itertools.islice(contentlines, MAX_CONTENTLINES):
        yield redact_contentline(contentline)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.DEFAULT_TIME_ZONE),
        "system_timezone": str(datetime.datetime.utcnow().astimezone().tzinfo),
    }
    store = hass.data[DOMAIN][config_entry.entry_id]
    ics = await store.async_load()
    payload["ics"] = "\n".join(redact_ics(ics))
    return payload
