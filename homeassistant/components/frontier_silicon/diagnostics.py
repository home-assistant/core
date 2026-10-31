"""Diagnostics support for Frontier Silicon."""

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from afsapi import FSApiError

from homeassistant.core import HomeAssistant

from . import FrontierSiliconConfigEntry


async def _query[_T](
    func: Callable[[], Awaitable[_T]], convert: Callable[[_T], Any] = lambda x: x
) -> Any:
    """Query a device value, returning the error type if it fails."""
    try:
        value = await func()
    except FSApiError as err:
        return {"error": type(err).__name__}
    return None if value is None else convert(value)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FrontierSiliconConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    afsapi = entry.runtime_data
    return {
        "version": await _query(afsapi.get_version),
        "rssi": await _query(afsapi.get_rssi),
        "power": await _query(afsapi.get_power),
        "play_status": await _query(afsapi.get_play_status, lambda s: s.name),
        "play_caps": await _query(
            afsapi.get_play_caps, lambda caps: [cap.name for cap in caps]
        ),
        "mode": await _query(afsapi.get_mode, asdict),
        "modes": await _query(
            afsapi.get_modes, lambda modes: [asdict(mode) for mode in modes]
        ),
        "eq_preset": await _query(afsapi.get_eq_preset, asdict),
        "equalisers": await _query(
            afsapi.get_equalisers, lambda eqs: [asdict(eq) for eq in eqs]
        ),
        "volume_steps": await _query(afsapi.get_volume_steps),
        "volume": await _query(afsapi.get_volume),
        "mute": await _query(afsapi.get_mute),
        "dst": await _query(afsapi.get_dst),
    }
