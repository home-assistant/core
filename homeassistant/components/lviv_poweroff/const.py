"""Constants for the Lviv Power Offline integration."""

from enum import StrEnum

DOMAIN = "lviv_poweroff"

POWEROFF_GROUP_CONF = "poweroff_group"

UPDATE_INTERVAL = 600


class PowerOffGroup(StrEnum):
    """PowerOff groups in Lviv oblast."""

    OneOne = "1.1"
    OneTwo = "1.2"
    TwoOne = "2.1"
    TwoTwo = "2.2"
    ThreeOne = "3.1"
    ThreeTwo = "3.2"
