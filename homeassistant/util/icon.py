"""Icon util methods."""
from typing import Optional


def icon_for_battery_level(battery_level: Optional[int]=None,
                           charging: bool=False) -> str:
    """Return a battery icon valid identifier."""
    icon = 'mdi:battery'
    if battery_level is None:
        return icon + '-unknown'
    if charging:
        icon += '-charging'
    if 20 <= battery_level < 100:
        icon += '-{}'.format(int(battery_level / 20) * 20)
    elif battery_level < 20:
        icon += '-outline'
    return icon
