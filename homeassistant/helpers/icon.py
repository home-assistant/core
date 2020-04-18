"""Icon helper methods."""
from typing import Optional


def icon_for_battery_level(
    battery_level: Optional[int] = None, charging: bool = False
) -> str:
    """Return a battery icon valid identifier."""
    icon = "mdi:battery"
    if battery_level is None:
        return f"{icon}-unknown"
    if charging and battery_level > 10:
        icon += "-charging-{}".format(int(round(battery_level / 20 - 0.01)) * 20)
    elif charging:
        icon += "-outline"
    elif battery_level <= 5:
        icon += "-alert"
    elif 5 < battery_level < 95:
        icon += "-{}".format(int(round(battery_level / 10 - 0.01)) * 10)
    return icon


def icon_for_signal_level(signal_level: Optional[int] = None) -> str:
    """Return a signal icon valid identifier."""
    if signal_level is None or signal_level == 0:
        return "mdi:signal-cellular-outline"
    if signal_level > 70:
        return "mdi:signal-cellular-3"
    if signal_level > 30:
        return "mdi:signal-cellular-2"
    return "mdi:signal-cellular-1"
