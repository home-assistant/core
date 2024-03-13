"""Provides functionality to interact with humidifier devices."""
from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.deprecation import (
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import (  # noqa: F401
    _DEPRECATED_DEVICE_CLASS_DEHUMIDIFIER,
    _DEPRECATED_DEVICE_CLASS_HUMIDIFIER,
    _DEPRECATED_SUPPORT_MODES,
    ATTR_ACTION,
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN,
    MODE_AUTO,
    MODE_AWAY,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierAction,
    HumidifierEntityFeature,
)

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property


_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)

ENTITY_ID_FORMAT = DOMAIN + ".{}"


class HumidifierDeviceClass(StrEnum):
    """Device class for humidifiers."""

    HUMIDIFIER = "humidifier"
    DEHUMIDIFIER = "dehumidifier"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(HumidifierDeviceClass))

# DEVICE_CLASSES below is deprecated as of 2021.12
# use the HumidifierDeviceClass enum instead.
DEVICE_CLASSES = [cls.value for cls in HumidifierDeviceClass]

# mypy: disallow-any-generics


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the humidifier is on based on the statemachine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up humidifier devices."""
    component = hass.data[DOMAIN] = EntityComponent[HumidifierEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_SET_MODE,
        {vol.Required(ATTR_MODE): cv.string},
        "async_set_mode",
        [HumidifierEntityFeature.MODES],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        {
            vol.Required(ATTR_HUMIDITY): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_humidity",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[HumidifierEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[HumidifierEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class HumidifierEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes humidifier entities."""

    device_class: HumidifierDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
    "action",
    "current_humidity",
    "target_humidity",
    "mode",
    "available_modes",
    "min_humidity",
    "max_humidity",
    "supported_features",
}


class HumidifierEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for humidifier entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {ATTR_MIN_HUMIDITY, ATTR_MAX_HUMIDITY, ATTR_AVAILABLE_MODES}
    )

    entity_description: HumidifierEntityDescription
    _attr_action: HumidifierAction | None = None
    _attr_available_modes: list[str] | None
    _attr_current_humidity: int | None = None
    _attr_device_class: HumidifierDeviceClass | None
    _attr_max_humidity: int = DEFAULT_MAX_HUMIDITY
    _attr_min_humidity: int = DEFAULT_MIN_HUMIDITY
    _attr_mode: str | None
    _attr_supported_features: HumidifierEntityFeature = HumidifierEntityFeature(0)
    _attr_target_humidity: int | None = None

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, int | list[str] | None] = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
        }

        if HumidifierEntityFeature.MODES in self.supported_features_compat:
            data[ATTR_AVAILABLE_MODES] = self.available_modes

        return data

    @cached_property
    def device_class(self) -> HumidifierDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        data: dict[str, int | str | None] = {}

        if self.action is not None:
            data[ATTR_ACTION] = self.action if self.is_on else HumidifierAction.OFF

        if self.current_humidity is not None:
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity

        if self.target_humidity is not None:
            data[ATTR_HUMIDITY] = self.target_humidity

        if HumidifierEntityFeature.MODES in self.supported_features_compat:
            data[ATTR_MODE] = self.mode

        return data

    @cached_property
    def action(self) -> HumidifierAction | None:
        """Return the current action."""
        return self._attr_action

    @cached_property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._attr_current_humidity

    @cached_property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._attr_target_humidity

    @cached_property
    def mode(self) -> str | None:
        """Return the current mode, e.g., home, auto, baby.

        Requires HumidifierEntityFeature.MODES.
        """
        return self._attr_mode

    @cached_property
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes.

        Requires HumidifierEntityFeature.MODES.
        """
        return self._attr_available_modes

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        raise NotImplementedError()

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""
        await self.hass.async_add_executor_job(self.set_mode, mode)

    @cached_property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @cached_property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self._attr_max_humidity

    @cached_property
    def supported_features(self) -> HumidifierEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def supported_features_compat(self) -> HumidifierEntityFeature:
        """Return the supported features as HumidifierEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is int:  # noqa: E721
            new_features = HumidifierEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features


# As we import deprecated constants from the const module, we need to add these two functions
# otherwise this module will be logged for using deprecated constants and not the custom component
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
