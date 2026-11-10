"""Diagnostics support for SleepIQ."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import SleepIQConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SleepIQConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Names, IDs and MAC addresses identify the account and are left out.
    return {
        "beds": [
            {
                "model": bed.model,
                "paused": bed.paused,
                "foundation": {
                    "type": bed.foundation.type,
                    "features": bed.foundation.features,
                    "actuators": len(bed.foundation.actuators),
                    "presets": len(bed.foundation.presets),
                    "lights": len(bed.foundation.lights),
                    "foot_warmers": len(bed.foundation.foot_warmers),
                    "core_climates": len(bed.foundation.core_climates),
                },
                "sleepers": [
                    {
                        "side": sleeper.side,
                        "in_bed": sleeper.in_bed,
                        "pressure": sleeper.pressure,
                        "sleep_number": sleeper.sleep_number,
                        "sleep_data": (
                            asdict(sleeper.sleep_data) if sleeper.sleep_data else None
                        ),
                    }
                    for sleeper in bed.sleepers
                ],
            }
            for bed in entry.runtime_data.client.beds.values()
        ]
    }
