"""Diagnostics support for pyLoad."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from yarl import URL

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import PyLoadConfigEntry, PyLoadData

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PyLoadConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    pyload_data: PyLoadData = config_entry.runtime_data.data

    return {
        "config_entry_data": {
            **async_redact_data(dict(config_entry.data), TO_REDACT),
            CONF_URL: URL(config_entry.data[CONF_URL]).with_host(REDACTED).human_repr(),
        },
        "pyload_data": asdict(pyload_data),
    }
