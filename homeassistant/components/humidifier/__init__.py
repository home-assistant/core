"""Provides functionality to interact with humidifier devices."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any, final

from propcache import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey

from .const import (  # noqa: F401
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
    MODE_BABY,
    MODE_BOOST,
    MODE_COMFORT,
    MODE_ECO,
    MODE_HOME,
    MODE_NORMAL,
    MODE_SLEEP,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierAction,
    HumidifierEntityFeature,
)

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[HumidifierEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


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
    component = hass.data[DATA_COMPONENT] = EntityComponent[HumidifierEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, None, "async_toggle")
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
        async_service_humidity_set,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
    _attr_current_humidity: float | None = None
    _attr_device_class: HumidifierDeviceClass | None
    _attr_max_humidity: float = DEFAULT_MAX_HUMIDITY
    _attr_min_humidity: float = DEFAULT_MIN_HUMIDITY
    _attr_mode: str | None
    _attr_supported_features: HumidifierEntityFeature = HumidifierEntityFeature(0)
    _attr_target_humidity: float | None = None

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, Any] = {
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
        data: dict[str, Any] = {}

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
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._attr_current_humidity

    @cached_property
    def target_humidity(self) -> float | None:
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
        raise NotImplementedError

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        raise NotImplementedError

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""
        await self.hass.async_add_executor_job(self.set_mode, mode)

    @cached_property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @cached_property
    def max_humidity(self) -> float:
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


async def async_service_humidity_set(
    entity: HumidifierEntity, service_call: ServiceCall
) -> None:
    """Handle set humidity service."""
    humidity = service_call.data[ATTR_HUMIDITY]
    min_humidity = entity.min_humidity
    max_humidity = entity.max_humidity
    _LOGGER.debug(
        "Check valid humidity %d in range %d - %d",
        humidity,
        min_humidity,
        max_humidity,
    )
    if humidity < min_humidity or humidity > max_humidity:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="humidity_out_of_range",
            translation_placeholders={
                "humidity": str(humidity),
                "min_humidity": str(min_humidity),
                "max_humidity": str(max_humidity),
            },
        )

    await entity.async_set_humidity(humidity)
