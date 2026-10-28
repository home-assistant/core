"""Diagnostics support for Denon AVR Network Receivers."""

from typing import Any

from homeassistant.const import CONF_MODEL, CONF_TYPE
from homeassistant.core import HomeAssistant

from . import DenonavrConfigEntry
from .const import CONF_MANUFACTURER

ENTRY_DATA_KEYS = (CONF_MANUFACTURER, CONF_MODEL, CONF_TYPE)

RECEIVER_ATTRIBUTES = (
    "manufacturer",
    "model_name",
    "receiver_type",
    "receiver_port",
    "telnet_available",
    "telnet_connected",
    "telnet_healthy",
)

ZONE_ATTRIBUTES = (
    "power",
    "state",
    "muted",
    "volume",
    "input_func",
    "input_func_list",
    "netaudio_func_list",
    "playing_func_list",
    "support_sound_mode",
    "sound_mode",
    "sound_mode_raw",
    "sound_mode_list",
    "support_tone_control",
    "dynamic_eq",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DenonavrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    receiver = entry.runtime_data
    return {
        "entry_data": {key: entry.data[key] for key in ENTRY_DATA_KEYS},
        "entry_options": dict(entry.options),
        "receiver": {attr: getattr(receiver, attr) for attr in RECEIVER_ATTRIBUTES},
        "zones": {
            name: {attr: getattr(zone, attr) for attr in ZONE_ATTRIBUTES}
            for name, zone in receiver.zones.items()
        },
    }
