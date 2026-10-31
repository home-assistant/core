"""Base entity for the Humidifier platform."""

from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription

from .const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntityCapabilityAttribute,
    HumidifierEntityFeature,
    HumidifierEntityStateAttribute,
)


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
    "target_humidity_step",
}


class HumidifierEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for humidifier entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            HumidifierEntityCapabilityAttribute.MIN_HUMIDITY,
            HumidifierEntityCapabilityAttribute.MAX_HUMIDITY,
            HumidifierEntityCapabilityAttribute.AVAILABLE_MODES,
            HumidifierEntityCapabilityAttribute.TARGET_HUMIDITY_STEP,
        }
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
    _attr_target_humidity_step: float | None = None

    @property
    @override
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        data: dict[str, Any] = {
            HumidifierEntityCapabilityAttribute.MIN_HUMIDITY: self.min_humidity,
            HumidifierEntityCapabilityAttribute.MAX_HUMIDITY: self.max_humidity,
        }
        if self.target_humidity_step is not None:
            data[HumidifierEntityCapabilityAttribute.TARGET_HUMIDITY_STEP] = (
                self.target_humidity_step
            )

        if HumidifierEntityFeature.MODES in self.supported_features:
            data[HumidifierEntityCapabilityAttribute.AVAILABLE_MODES] = (
                self.available_modes
            )

        return data

    @cached_property
    @override
    def device_class(self) -> HumidifierDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        data: dict[str, Any] = {}

        if self.action is not None:
            data[HumidifierEntityStateAttribute.ACTION] = (
                self.action if self.is_on else HumidifierAction.OFF
            )

        if self.current_humidity is not None:
            data[HumidifierEntityStateAttribute.CURRENT_HUMIDITY] = (
                self.current_humidity
            )

        if self.target_humidity is not None:
            data[HumidifierEntityStateAttribute.HUMIDITY] = self.target_humidity

        if HumidifierEntityFeature.MODES in self.supported_features:
            data[HumidifierEntityStateAttribute.MODE] = self.mode

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
    def target_humidity_step(self) -> float | None:
        """Return the supported step of humidity."""
        return self._attr_target_humidity_step

    @cached_property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""
        return self._attr_min_humidity

    @cached_property
    def max_humidity(self) -> float:
        """Return the maximum humidity."""
        return self._attr_max_humidity

    @cached_property
    @override
    def supported_features(self) -> HumidifierEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
