"""Diagnostics support for Withings."""
from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.webhook import async_generate_url as webhook_generate_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from . import CONF_CLOUDHOOK_URL, WithingsData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
    url = URL(webhook_url)
    has_valid_external_webhook_url = url.scheme == "https" and url.port == 443

    has_cloudhooks = CONF_CLOUDHOOK_URL in entry.data

    withings_data: WithingsData = hass.data[DOMAIN][entry.entry_id]

    return {
        "has_valid_external_webhook_url": has_valid_external_webhook_url,
        "has_cloudhooks": has_cloudhooks,
        "webhooks_connected": withings_data.measurement_coordinator.webhooks_connected,
        "received_measurements": list(withings_data.measurement_coordinator.data),
        "received_sleep_data": withings_data.sleep_coordinator.data is not None,
        "received_workout_data": withings_data.workout_coordinator.data is not None,
        "received_activity_data": withings_data.activity_coordinator.data is not None,
    }
