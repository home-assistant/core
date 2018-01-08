"""Icon helper methods."""
from typing import Optional


def icon_for_battery_level(battery_level: Optional[int]=None,
                           charging: bool=False) -> str:
    """Return a battery icon valid identifier."""
    icon = 'mdi:battery'
    if battery_level is None:
        return icon + '-unknown'
    if charging and battery_level > 10:
        icon += '-charging-{}'.format(
            int(round(battery_level / 20 - .01)) * 20)
    elif charging:
        icon += '-outline'
    elif battery_level <= 5:
        icon += '-alert'
    elif 5 < battery_level < 95:
        icon += '-{}'.format(int(round(battery_level / 10 - .01)) * 10)
    return icon
