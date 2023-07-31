"""Provides functionality to interact with humidifier devices."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any, final

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
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import (  # noqa: F401
    ATTR_ACTION,
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    DOMAIN,
    MODE_AUTO,
    MODE_AWAY,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SUPPORT_MODES,
    HumidifierAction,
    HumidifierEntityFeature,
)

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
def is_on(hass, entity_id):
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


@dataclass
class HumidifierEntityDescription(ToggleEntityDescription):
    """A class that describes humidifier entities."""

    device_class: HumidifierDeviceClass | None = None


class HumidifierEntity(ToggleEntity):
    """Base class for humidifier entities."""

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

        if self.supported_features & HumidifierEntityFeature.MODES:
            data[ATTR_AVAILABLE_MODES] = self.available_modes

        return data

    @property
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

        if self.supported_features & HumidifierEntityFeature.MODES:
            data[ATTR_MODE] = self.mode

        return data

    @property
    def action(self) -> HumidifierAction | None:
        """Return the current action."""
        return self._attr_action

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._attr_current_humidity

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._attr_target_humidity

    @property
    def mode(self) -> str | None:
        """Return the current mode, e.g., home, auto, baby.

        Requires HumidifierEntityFeature.MODES.
        """
        return self._attr_mode

    @property
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

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self._attr_max_humidity

    @property
    def supported_features(self) -> HumidifierEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
