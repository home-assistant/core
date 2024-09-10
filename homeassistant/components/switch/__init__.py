"""Component to interface with switches that can be controlled remotely."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from functools import cached_property, partial
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


class SwitchDeviceClass(StrEnum):
    """Device class for switches."""

    OUTLET = "outlet"
    SWITCH = "switch"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(SwitchDeviceClass))

# DEVICE_CLASS* below are deprecated as of 2021.12
# use the SwitchDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in SwitchDeviceClass]
_DEPRECATED_DEVICE_CLASS_OUTLET = DeprecatedConstantEnum(
    SwitchDeviceClass.OUTLET, "2025.1"
)
_DEPRECATED_DEVICE_CLASS_SWITCH = DeprecatedConstantEnum(
    SwitchDeviceClass.SWITCH, "2025.1"
)

# mypy: disallow-any-generics


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the switch is on based on the statemachine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for switches."""
    component = hass.data[DOMAIN] = EntityComponent[SwitchEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[SwitchEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[SwitchEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class SwitchEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes switch entities."""

    device_class: SwitchDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
}


class SwitchEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for switch entities."""

    entity_description: SwitchEntityDescription
    _attr_device_class: SwitchDeviceClass | None

    @cached_property
    def device_class(self) -> SwitchDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
