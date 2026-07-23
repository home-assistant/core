"""Mapping from Beatbot HA `interfaceInfo` keys to `BeatbotDeviceData` fields.

The batch state endpoint (`/devices/state/ha`) returns per-device runtime values
keyed by HA entity-shape `interfaceInfo` strings (e.g. `vacuum.state`,
`vacuum.battery`). This module translates those keys onto the fixed
`BeatbotDeviceData` schema consumed by the existing entities.
"""

from ..models import BeatbotDeviceData

# interfaceInfo (server-side HA capability key) -> BeatbotDeviceData field.
# `versions` has no corresponding interfaceInfo key and is not mapped here.
# `work_mode` feeds the work-mode select entity (read from `select.work_mode`
# state, set via the `select.work_mode` action).
HA_STATE_FIELD_MAP: dict[str, str] = {
    "vacuum.state": "work_status",
    "vacuum.battery": "battery_level",
    "sensor.error": "error_code",
    "select.work_mode": "work_mode",
    "switch.child_lock": "child_lock",
    "switch.voice_disturb": "voice_disturb",
}


def apply_state(
    device: BeatbotDeviceData,
    states: dict | None,
    is_online: bool | None,
) -> BeatbotDeviceData:
    """Overlay batch-state values onto a device in place.

    `is_online` falls back to the device's existing value when the state
    payload does not carry it.
    """
    for iface, value in (states or {}).items():
        field = HA_STATE_FIELD_MAP.get(iface)
        if field is not None and hasattr(device, field):
            setattr(device, field, value)
    if is_online is not None:
        device.is_online = bool(is_online)
    return device
