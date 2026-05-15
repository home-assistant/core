"""Diagnostics support for iTach IP2IR."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {"device_id", "unique_id", "uuid"}


def _extract_client(runtime_data: Any) -> Any | None:
    """Extract client from runtime_data safely."""
    if runtime_data is None:
        return None

    # Tests: FakeClient directly
    if hasattr(runtime_data, "async_get_version"):
        return runtime_data

    # Production: wrapper object
    if hasattr(runtime_data, "client"):
        client = runtime_data.client
        if hasattr(client, "async_get_version"):
            return client

    return None


def _runtime_value(runtime_data: Any, key: str, fallback: Any = None) -> Any:
    """Return a value from runtime data when available, else fallback."""
    if runtime_data is None:
        return fallback

    return getattr(runtime_data, key, fallback)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = getattr(entry, "runtime_data", None)

    device: dict[str, Any] = {
        "host": _runtime_value(runtime_data, "host", entry.data.get("host")),
        "port": _runtime_value(runtime_data, "port", entry.data.get("port")),
        "device_id": entry.unique_id,
        "ir_module": _runtime_value(
            runtime_data,
            "ir_module",
            entry.data.get("ir_module"),
        ),
        "ir_ports": _runtime_value(
            runtime_data,
            "ir_ports",
            entry.data.get("ir_ports"),
        ),
        "ir_enabled_ports": _runtime_value(
            runtime_data,
            "ir_enabled_ports",
            entry.data.get("ir_enabled_ports"),
        ),
        "ir_connector_modes": _runtime_value(
            runtime_data,
            "ir_connector_modes",
            entry.data.get("ir_connector_modes"),
        ),
        "firmware_version": None,
        "firmware_error": None,
    }

    client = _extract_client(runtime_data)

    if client is not None:
        try:
            module = device.get("ir_module") or 1
            device["firmware_version"] = await client.async_get_version(module)
        except Exception as err:  # noqa: BLE001
            device["firmware_error"] = str(err)

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "domain": entry.domain,
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
            },
            TO_REDACT,
        ),
        "device": async_redact_data(device, TO_REDACT),
    }
