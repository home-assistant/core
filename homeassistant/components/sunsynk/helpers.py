"""Shared helpers for the SunSynk integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from . import SunSynkCoordinator


def extract_value(obj: Any, key: str) -> Any | None:
    """Extract a value from an object by key, trying multiple access patterns."""
    val = getattr(obj, key, None)
    if val is not None:
        return val

    if hasattr(obj, "__dict__"):
        val = obj.__dict__.get(key)
        if val is not None:
            return val

    if hasattr(obj, "model_extra") and obj.model_extra:
        val = obj.model_extra.get(key)
        if val is not None:
            return val

    if isinstance(obj, dict):
        return cast(dict[str, Any], obj).get(key)

    return None


def safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except ValueError, TypeError:
        return None


def get_inv_data(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
) -> dict[str, Any] | None:
    """Get inverter data dict from coordinator."""
    if not coordinator.data:
        return None
    plant = coordinator.data.get("plants", {}).get(plant_id)
    if not plant:
        return None
    result: dict[str, Any] | None = plant.get("inverters", {}).get(sn)
    return result


def get_source_obj(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
    source_type: str,
) -> Any | None:
    """Get a source object (battery, grid, etc.) from inverter data."""
    inv_data = get_inv_data(coordinator, plant_id, sn)
    if not inv_data:
        return None
    return inv_data.get(source_type)


def get_inverter_settings(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
) -> Any | None:
    """Get the inverter settings object from coordinator data."""
    inv_data = get_inv_data(coordinator, plant_id, sn)
    if not inv_data:
        return None
    return inv_data.get("settings")


def inverter_device_info(plant_id: int, sn: str) -> DeviceInfo:
    """Return DeviceInfo for an inverter."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"inverter_{sn}")},
        name=f"SunSynk Inverter {sn}",
        manufacturer="SunSynk",
        model="Inverter",
        serial_number=sn,
        via_device=(DOMAIN, f"plant_{plant_id}"),
    )
