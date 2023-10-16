"""Diagnostics support for Withings."""
from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.webhook import async_generate_url as webhook_generate_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from . import (
    CONF_CLOUDHOOK_URL,
    WithingsMeasurementDataUpdateCoordinator,
    WithingsSleepDataUpdateCoordinator,
)
from .const import DOMAIN, MEASUREMENT_COORDINATOR, SLEEP_COORDINATOR


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
    url = URL(webhook_url)
    has_valid_external_webhook_url = url.scheme == "https" and url.port == 443

    has_cloudhooks = CONF_CLOUDHOOK_URL in entry.data

    measurement_coordinator: WithingsMeasurementDataUpdateCoordinator = hass.data[
        DOMAIN
    ][entry.entry_id][MEASUREMENT_COORDINATOR]
    sleep_coordinator: WithingsSleepDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ][SLEEP_COORDINATOR]

    return {
        "has_valid_external_webhook_url": has_valid_external_webhook_url,
        "has_cloudhooks": has_cloudhooks,
        "webhooks_connected": measurement_coordinator.webhooks_connected,
        "received_measurements": list(measurement_coordinator.data),
        "received_sleep_data": sleep_coordinator.data is not None,
    }
