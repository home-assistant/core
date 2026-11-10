"""Diagnostics support for the A Better Routeplanner integration."""

from dataclasses import asdict
import re
from typing import Any

from aioabrp import Metric

from homeassistant.core import HomeAssistant

from .coordinator import AbrpConfigEntry

# Positional metrics place the vehicle, so only their time and provider are shown.
POSITIONAL_METRICS = {
    Metric.LOCATION,
    Metric.MAP_INFO,
    Metric.HEADING,
    Metric.ELEVATION,
}

# Stream error reasons can quote the request URL, which lists the vehicle ids.
_URL = re.compile(r"https?://\S+")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AbrpConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.telemetry_coordinator
    event = coordinator.last_connection_event
    vehicles: list[dict[str, Any]] = []
    for raw, display in entry.runtime_data.garage_coordinator.data:
        metrics: dict[str, dict[str, Any]] = {}
        if (telemetry := coordinator.data.get(raw.vehicle_id)) is not None:
            for metric, metric_value in telemetry.items():
                item: dict[str, Any] = {
                    "time": metric_value.time,
                    "provider": metric_value.provider,
                }
                # The type check keeps a future struct-valued metric out too.
                if metric not in POSITIONAL_METRICS and isinstance(
                    metric_value.value, (int, float, str)
                ):
                    item["value"] = metric_value.value
                metrics[metric.value] = item
        vehicles.append(
            {
                "vehicle_model": raw.vehicle_model,
                "display": asdict(display) if display is not None else None,
                "metrics": metrics,
            }
        )
    token = entry.data["token"]
    return {
        "entry": {
            "auth_implementation": entry.data["auth_implementation"],
            "token": {
                "token_type": token["token_type"],
                "expires_at": token["expires_at"],
            },
        },
        "stream": {
            "state": event.state.value if event is not None else None,
            "reason": (
                _URL.sub("<url>", event.reason)
                if event is not None and event.reason is not None
                else None
            ),
            "auth_failed": coordinator.stream_auth_failed,
        },
        "vehicles": vehicles,
    }
