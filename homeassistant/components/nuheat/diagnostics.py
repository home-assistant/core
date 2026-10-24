"""Allowlisted diagnostics from cached NuHeat state only."""

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from . import NuHeatConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NuHeatConfigEntry
) -> dict[str, Any]:
    """Describe local health without serializing entries, models or exceptions."""
    try:
        sdk_version = await hass.async_add_executor_job(version, "chemelex-nuheat")
    except PackageNotFoundError:
        sdk_version = None

    result: dict[str, Any] = {
        "versions": {"core": HA_VERSION, "sdk": sdk_version},
        "entry_state": entry.state.value,
        "runtime": None,
    }
    if (runtime := getattr(entry, "runtime_data", None)) is None:
        return result

    coordinator = runtime.coordinator
    result["runtime"] = {
        "availability": {
            "last_update_success": coordinator.last_update_success,
            "known_devices": len(coordinator.data or {}),
            "available_devices": sum(
                coordinator.is_thermostat_available(serial)
                for serial in coordinator.data or {}
            ),
        },
        "cooldown_active": coordinator.cooldown_remaining > 0,
        "confirmation": coordinator.confirmation_status,
    }
    return result
