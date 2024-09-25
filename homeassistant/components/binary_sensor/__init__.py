"""Component to interface with binary sensors."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from functools import cached_property, partial
import logging
from typing import Literal, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

DOMAIN = "binary_sensor"
DATA_COMPONENT: HassKey[EntityComponent[BinarySensorEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


class BinarySensorDeviceClass(StrEnum):
    """Device class for binary sensors."""

    # On means low, Off means normal
    BATTERY = "battery"

    # On means charging, Off means not charging
    BATTERY_CHARGING = "battery_charging"

    # On means carbon monoxide detected, Off means no carbon monoxide (clear)
    CO = "carbon_monoxide"

    # On means cold, Off means normal
    COLD = "cold"

    # On means connected, Off means disconnected
    CONNECTIVITY = "connectivity"

    # On means open, Off means closed
    DOOR = "door"

    # On means open, Off means closed
    GARAGE_DOOR = "garage_door"

    # On means gas detected, Off means no gas (clear)
    GAS = "gas"

    # On means hot, Off means normal
    HEAT = "heat"

    # On means light detected, Off means no light
    LIGHT = "light"

    # On means open (unlocked), Off means closed (locked)
    LOCK = "lock"

    # On means wet, Off means dry
    MOISTURE = "moisture"

    # On means motion detected, Off means no motion (clear)
    MOTION = "motion"

    # On means moving, Off means not moving (stopped)
    MOVING = "moving"

    # On means occupied, Off means not occupied (clear)
    OCCUPANCY = "occupancy"

    # On means open, Off means closed
    OPENING = "opening"

    # On means plugged in, Off means unplugged
    PLUG = "plug"

    # On means power detected, Off means no power
    POWER = "power"

    # On means home, Off means away
    PRESENCE = "presence"

    # On means problem detected, Off means no problem (OK)
    PROBLEM = "problem"

    # On means running, Off means not running
    RUNNING = "running"

    # On means unsafe, Off means safe
    SAFETY = "safety"

    # On means smoke detected, Off means no smoke (clear)
    SMOKE = "smoke"

    # On means sound detected, Off means no sound (clear)
    SOUND = "sound"

    # On means tampering detected, Off means no tampering (clear)
    TAMPER = "tamper"

    # On means update available, Off means up-to-date
    UPDATE = "update"

    # On means vibration detected, Off means no vibration
    VIBRATION = "vibration"

    # On means open, Off means closed
    WINDOW = "window"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(BinarySensorDeviceClass))

# DEVICE_CLASS* below are deprecated as of 2021.12
# use the BinarySensorDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in BinarySensorDeviceClass]
_DEPRECATED_DEVICE_CLASS_BATTERY = DeprecatedConstantEnum(
    BinarySensorDeviceClass.BATTERY, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_BATTERY_CHARGING = DeprecatedConstantEnum(
    BinarySensorDeviceClass.BATTERY_CHARGING, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_CO = DeprecatedConstantEnum(
    BinarySensorDeviceClass.CO, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_COLD = DeprecatedConstantEnum(
    BinarySensorDeviceClass.COLD, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_CONNECTIVITY = DeprecatedConstantEnum(
    BinarySensorDeviceClass.CONNECTIVITY, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_DOOR = DeprecatedConstantEnum(
    BinarySensorDeviceClass.DOOR, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_GARAGE_DOOR = DeprecatedConstantEnum(
    BinarySensorDeviceClass.GARAGE_DOOR, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_GAS = DeprecatedConstantEnum(
    BinarySensorDeviceClass.GAS, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_HEAT = DeprecatedConstantEnum(
    BinarySensorDeviceClass.HEAT, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_LIGHT = DeprecatedConstantEnum(
    BinarySensorDeviceClass.LIGHT, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_LOCK = DeprecatedConstantEnum(
    BinarySensorDeviceClass.LOCK, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_MOISTURE = DeprecatedConstantEnum(
    BinarySensorDeviceClass.MOISTURE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_MOTION = DeprecatedConstantEnum(
    BinarySensorDeviceClass.MOTION, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_MOVING = DeprecatedConstantEnum(
    BinarySensorDeviceClass.MOVING, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_OCCUPANCY = DeprecatedConstantEnum(
    BinarySensorDeviceClass.OCCUPANCY, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_OPENING = DeprecatedConstantEnum(
    BinarySensorDeviceClass.OPENING, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_PLUG = DeprecatedConstantEnum(
    BinarySensorDeviceClass.PLUG, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_POWER = DeprecatedConstantEnum(
    BinarySensorDeviceClass.POWER, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_PRESENCE = DeprecatedConstantEnum(
    BinarySensorDeviceClass.PRESENCE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_PROBLEM = DeprecatedConstantEnum(
    BinarySensorDeviceClass.PROBLEM, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_RUNNING = DeprecatedConstantEnum(
    BinarySensorDeviceClass.RUNNING, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_SAFETY = DeprecatedConstantEnum(
    BinarySensorDeviceClass.SAFETY, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_SMOKE = DeprecatedConstantEnum(
    BinarySensorDeviceClass.SMOKE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_SOUND = DeprecatedConstantEnum(
    BinarySensorDeviceClass.SOUND, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_TAMPER = DeprecatedConstantEnum(
    BinarySensorDeviceClass.TAMPER, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_UPDATE = DeprecatedConstantEnum(
    BinarySensorDeviceClass.UPDATE, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_VIBRATION = DeprecatedConstantEnum(
    BinarySensorDeviceClass.VIBRATION, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_WINDOW = DeprecatedConstantEnum(
    BinarySensorDeviceClass.WINDOW, "2025.1"
)

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for binary sensors."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[BinarySensorEntity](
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class BinarySensorEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes binary sensor entities."""

    device_class: BinarySensorDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "is_on",
}


class BinarySensorEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Represent a binary sensor."""

    entity_description: BinarySensorEntityDescription
    _attr_device_class: BinarySensorDeviceClass | None
    _attr_is_on: bool | None = None
    _attr_state: None = None

    async def async_internal_added_to_hass(self) -> None:
        """Call when the binary sensor entity is added to hass."""
        await super().async_internal_added_to_hass()
        if self.entity_category == EntityCategory.CONFIG:
            raise HomeAssistantError(
                f"Entity {self.entity_id} cannot be added as the entity category is set to config"
            )

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For binary sensors this is True if the entity has a device class.
        """
        return self.device_class is not None

    @cached_property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._attr_is_on

    @final
    @property
    def state(self) -> Literal["on", "off"] | None:
        """Return the state of the binary sensor."""
        if (is_on := self.is_on) is None:
            return None
        return STATE_ON if is_on else STATE_OFF


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
