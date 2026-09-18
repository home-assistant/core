"""Constants for the Switch integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

import probatio

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import SwitchEntity

DOMAIN: Final = "switch"
DATA_COMPONENT: HassKey[EntityComponent[SwitchEntity]] = HassKey(DOMAIN)


class SwitchDeviceClass(StrEnum):
    """Device class for switches."""

    OUTLET = "outlet"
    SWITCH = "switch"


DEVICE_CLASSES_SCHEMA = probatio.All(probatio.Lower, probatio.Coerce(SwitchDeviceClass))
