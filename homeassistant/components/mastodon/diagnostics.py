"""Diagnostics support for the Mastodon integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import MastodonConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MastodonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data

    instance: dict = await hass.async_add_executor_job(data.client.instance)

    return {
        "instance": instance,
        "account": data.coordinator.data,
    }
