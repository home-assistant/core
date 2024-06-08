"""Diagnostics support for Withings."""

from __future__ import annotations

from typing import Any

from yarl import URL

from homeassistant.components.webhook import async_generate_url as webhook_generate_url
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from . import CONF_CLOUDHOOK_URL, WithingsConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WithingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
    url = URL(webhook_url)
    has_valid_external_webhook_url = url.scheme == "https" and url.port == 443

    has_cloudhooks = CONF_CLOUDHOOK_URL in entry.data

    withings_data = entry.runtime_data

    received_measurements: dict[str, list[str] | None] = {}
    for measurement in withings_data.measurement_coordinator.data:
        measurement_name = measurement[0].name.lower()
        position = measurement[1]
        if position is None:
            received_measurements[measurement[0].name.lower()] = None
            continue
        position_name = position.name.lower()
        if measurement_name in received_measurements:
            lst = received_measurements[measurement_name]
            assert lst is not None
            lst.append(position_name)
        else:
            received_measurements[measurement_name] = [position_name]

    return {
        "has_valid_external_webhook_url": has_valid_external_webhook_url,
        "has_cloudhooks": has_cloudhooks,
        "webhooks_connected": withings_data.measurement_coordinator.webhooks_connected,
        "received_measurements": received_measurements,
        "received_sleep_data": withings_data.sleep_coordinator.data is not None,
        "received_workout_data": withings_data.workout_coordinator.data is not None,
        "received_activity_data": withings_data.activity_coordinator.data is not None,
    }
