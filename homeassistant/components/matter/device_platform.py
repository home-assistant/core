"""All mappings of Matter devices to Home Assistant platforms."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .light import DEVICE_ENTITY as LIGHT_DEVICE_ENTITY
from .sensor import DEVICE_ENTITY as SENSOR_DEVICE_ENTITY

if TYPE_CHECKING:
    from matter_server.common.models.device_types import DeviceType

    from .entity import MatterEntityDescriptionBaseClass


DEVICE_PLATFORM: dict[
    Platform,
    dict[
        type[DeviceType],
        MatterEntityDescriptionBaseClass | list[MatterEntityDescriptionBaseClass],
    ],
] = {
    Platform.LIGHT: LIGHT_DEVICE_ENTITY,
    Platform.SENSOR: SENSOR_DEVICE_ENTITY,
}
