"""Icon helper methods."""
from __future__ import annotations


def icon_for_battery_level(
    battery_level: int | None = None, charging: bool = False
) -> str:
    """Return a battery icon valid identifier."""
    icon = "mdi:battery"
    if battery_level is None:
        return f"{icon}-unknown"
    if charging and battery_level > 10:
        icon += f"-charging-{int(round(battery_level / 20 - 0.01)) * 20}"
    elif charging:
        icon += "-outline"
    elif battery_level <= 5:
        icon += "-alert"
    elif 5 < battery_level < 95:
        icon += f"-{int(round(battery_level / 10 - 0.01)) * 10}"
    return icon


def icon_for_signal_level(signal_level: int | None = None) -> str:
    """Return a signal icon valid identifier."""
    if signal_level is None or signal_level == 0:
        return "mdi:signal-cellular-outline"
    if signal_level > 70:
        return "mdi:signal-cellular-3"
    if signal_level > 30:
        return "mdi:signal-cellular-2"
    return "mdi:signal-cellular-1"


def icon_for_volume_level(
    volume_level: int | None = None, volume_mute: bool = False
) -> str:
    """Return a volume icon valid identifier."""
    icon = "mdi:volume"
    if volume_level is None:
        icon += "-variant-off"
    elif volume_mute:
        icon += "-mute"
    elif volume_level == 0:
        icon += "-off"
    elif volume_level <= 35:
        icon += "-low"
    elif volume_level <= 70:
        icon += "-medium"
    elif volume_level > 70:
        icon += "-high"
    return icon
