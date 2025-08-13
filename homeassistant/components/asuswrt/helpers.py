"""Helpers for AsusWRT integration."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", dict[str, Any], list[Any], None)

TRANSLATION_MAP = {
    "wan_rx": "sensor_rx_bytes",
    "wan_tx": "sensor_tx_bytes",
    "total_usage": "cpu_total_usage",
    "usage": "mem_usage_perc",
    "free": "mem_free",
    "used": "mem_used",
    "wan_rx_speed": "sensor_rx_rates",
    "wan_tx_speed": "sensor_tx_rates",
    "2ghz": "2.4GHz",
    "5ghz": "5.0GHz",
    "5ghz2": "5.0GHz_2",
    "6ghz": "6.0GHz",
    "cpu": "CPU",
    "datetime": "sensor_last_boot",
    "uptime": "sensor_uptime",
    **{f"{num}_usage": f"cpu{num}_usage" for num in range(1, 9)},
    **{f"load_avg_{load}": f"sensor_load_avg{load}" for load in ("1", "5", "15")},
}


def clean_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Cleans dictionary from None values.

    The `state` key is always preserved regardless of its value.
    """

    return {k: v for k, v in raw.items() if v is not None or k.endswith("state")}


def translate_to_legacy(raw: T) -> T:
    """Translate raw data to legacy format for dicts and lists."""

    if raw is None:
        return None

    if isinstance(raw, dict):
        return {TRANSLATION_MAP.get(k, k): v for k, v in raw.items()}

    if isinstance(raw, list):
        return [
            TRANSLATION_MAP[item]
            if isinstance(item, str) and item in TRANSLATION_MAP
            else item
            for item in raw
        ]

    return raw
