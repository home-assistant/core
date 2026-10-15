"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

import probatio

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import ButtonEntity

DOMAIN: Final = "button"
DATA_COMPONENT: HassKey[EntityComponent[ButtonEntity]] = HassKey(DOMAIN)

SERVICE_PRESS = "press"


class ButtonDeviceClass(StrEnum):
    """Device class for buttons."""

    IDENTIFY = "identify"
    RESTART = "restart"
    UPDATE = "update"


DEVICE_CLASSES_SCHEMA = probatio.All(probatio.Lower, probatio.Coerce(ButtonDeviceClass))
