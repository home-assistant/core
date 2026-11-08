"""Constants for the Valve entity platform."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

import probatio

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import ValveEntity

DOMAIN: Final = "valve"
DATA_COMPONENT: HassKey[EntityComponent[ValveEntity]] = HassKey(DOMAIN)

ATTR_POSITION = "position"


class ValveEntityStateAttribute(StrEnum):
    """State attributes for valve entities."""

    IS_CLOSED = "is_closed"
    CURRENT_POSITION = "current_position"


class ValveDeviceClass(StrEnum):
    """Device class for valve."""

    # Refer to the valve dev docs for device class descriptions
    WATER = "water"
    GAS = "gas"


class ValveEntityFeature(IntFlag):
    """Supported features of the valve entity."""

    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8


class ValveState(StrEnum):
    """State of Valve entities."""

    OPENING = "opening"
    CLOSING = "closing"
    CLOSED = "closed"
    OPEN = "open"


DEVICE_CLASSES_SCHEMA = probatio.All(probatio.Lower, probatio.Coerce(ValveDeviceClass))


class ValveService(StrEnum):
    """Store keys for valve services."""

    CLOSE = "close_valve"
    OPEN = "open_valve"
    SET_POSITION = "set_valve_position"
    STOP = "stop_valve"
    TOGGLE = "toggle"


class ValveServiceArgument(StrEnum):
    """Store keys for valve service arguments."""

    POSITION = "position"
