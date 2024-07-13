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

    positional_measurements: dict[str, list[str]] = {}
    measurements: list[str] = []

    for measurement in withings_data.measurement_coordinator.data:
        measurement_type, measurement_position = measurement
        measurement_type_name = measurement_type.name.lower()
        if measurement_position is not None:
            measurement_position_name = measurement_position.name.lower()
            if measurement_type_name not in positional_measurements:
                positional_measurements[measurement_type_name] = []
            positional_measurements[measurement_type_name].append(
                measurement_position_name
            )
        else:
            measurements.append(measurement_type_name)

    return {
        "has_valid_external_webhook_url": has_valid_external_webhook_url,
        "has_cloudhooks": has_cloudhooks,
        "webhooks_connected": withings_data.measurement_coordinator.webhooks_connected,
        "received_measurements": {
            "positional": positional_measurements,
            "non_positional": measurements,
        },
        "received_sleep_data": withings_data.sleep_coordinator.data is not None,
        "received_workout_data": withings_data.workout_coordinator.data is not None,
        "received_activity_data": withings_data.activity_coordinator.data is not None,
    }
