"""Shared entity helpers for the Kii Audio integration."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import KiiAudioCoordinator


def zone_name(zone: dict[str, Any]) -> str | None:
    """Return the configured zone name."""
    settings = zone.get("settings")
    if not isinstance(settings, dict):
        return None
    name = settings.get("zoneName")
    return name if isinstance(name, str) else None


def zone_model(zone: dict[str, Any]) -> str | None:
    """Return a model summary for devices in a Kii zone."""
    devices = zone.get("devices")
    if not isinstance(devices, list):
        return None

    models = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        model = device.get("modelName")
        if isinstance(model, str) and model and model not in models:
            models.append(model)

    if not models:
        return None
    if len(models) == 1:
        return models[0]
    return f"Mixed ({', '.join(models)})"


def zone_device_info(
    coordinator: KiiAudioCoordinator,
    zone_id: str,
    zone: dict[str, Any],
) -> DeviceInfo:
    """Return HA device info for a Kii zone."""
    system_id = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
    return DeviceInfo(
        identifiers={(DOMAIN, f"{system_id}_{zone_id}")},
        manufacturer="Kii Audio GmbH",
        model=zone_model(zone),
        name=zone_name(zone) or zone_id,
    )
