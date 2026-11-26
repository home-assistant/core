"""Diagnostics support for Sonarr."""

from dataclasses import fields
from typing import Any

from yarl import URL

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import SonarrConfigEntry, SonarrDataUpdateCoordinator

TO_REDACT = {CONF_API_KEY}


def _redact_url_credentials(url: str) -> str:
    """Redact the user and password of a URL, for example of a proxy."""
    parsed = URL(url)
    # A token can be the password without a user, which yarl reports as no user
    if parsed.user is None and parsed.password is None:
        return url
    return str(parsed.with_user(REDACTED).with_password(None))


def _model_to_dict(model: Any) -> dict[str, Any]:
    # aiopyarr only sets the fields that the Sonarr response contains.
    return {
        field.name: getattr(model, field.name)
        for field in fields(model)
        if hasattr(model, field.name)
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SonarrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    coordinators: dict[str, SonarrDataUpdateCoordinator[Any]] = {
        "commands": data.commands,
        "diskspace": data.diskspace,
        "queue": data.queue,
        "series": data.series,
        "status": data.status,
        "upcoming": data.upcoming,
        "wanted": data.wanted,
    }

    entry_data = async_redact_data(entry.data, TO_REDACT)
    entry_data[CONF_URL] = _redact_url_credentials(entry_data[CONF_URL])

    return {
        "entry_data": entry_data,
        "entry_options": dict(entry.options),
        "last_update_success": {
            name: coordinator.last_update_success
            for name, coordinator in coordinators.items()
        },
        "disks": [_model_to_dict(disk) for disk in data.diskspace.data],
    }
