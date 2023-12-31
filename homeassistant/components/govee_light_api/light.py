"""Govee Light."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from govee_local_api import GoveeDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capability import (
    GOVEE_COORDINATORS_MAPPER,
    GOVEE_DEVICE_CAPABILITIES,
    GoveeLightCapabilities,
)
from .const import DOMAIN, MANUFACTURER
from .coordinator import GoveeLocalApiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Govee light setup."""

    coordinator: GoveeLocalApiCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        GoveeLight(coordinator, device) for device in coordinator.devices
    )

    def discovery_callback(device: GoveeDevice, is_new: bool) -> bool:
        if is_new:
            entity = GoveeLight(coordinator, device)
            async_add_entities([entity])
        return True

    await coordinator.set_discovery_callback(discovery_callback)


class GoveeLight(CoordinatorEntity, LightEntity):
    """Govee Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: GoveeLocalApiCoordinator,
        device: GoveeDevice,
    ) -> None:
        """Govee Light constructor."""

        super().__init__(coordinator)
        self._device = device
        self._device.set_update_callback(self._update_callback)

        capabilities: set[GoveeLightCapabilities] = GOVEE_DEVICE_CAPABILITIES.get(
            device.sku, set()
        )

        self._attr_unique_id = device.fingerprint

        color_modes = set()
        if GoveeLightCapabilities.COLOR_RGB in capabilities:
            color_modes.add(ColorMode.RGB)
        if GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE in capabilities:
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_max_color_temp_kelvin = 9000
            self._attr_min_color_temp_kelvin = 2000
        if GoveeLightCapabilities.BRIGHTNESS in capabilities:
            color_modes.add(ColorMode.BRIGHTNESS)

        if len(color_modes) == 0:
            color_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = color_modes
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, device.fingerprint)
            },
            name=device.sku,
            manufacturer=MANUFACTURER,
            model=device.sku,
            connections={(CONNECTION_NETWORK_MAC, device.fingerprint)},
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self._device.on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return int((self._device.brightness / 100.0) * 255.0)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.temperature_color

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color."""
        return self._device.rgb_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode."""
        if (
            self._device.temperature_color is not None
            and self._device.temperature_color > 0
        ):
            return ColorMode.COLOR_TEMP
        if self._device.rgb_color is not None and any(self._device.rgb_color):
            return ColorMode.RGB

        if (
            self._attr_supported_color_modes
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if not self.is_on or not kwargs:
            await self.coordinator.turn_on(self._device)

        if ATTR_BRIGHTNESS in kwargs:
            brightness: int = int((float(kwargs[ATTR_BRIGHTNESS]) / 255.0) * 100.0)
            await self.coordinator.set_brightness(self._device, brightness)

        if ATTR_RGB_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGB
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self.coordinator.set_rgb_color(self._device, red, green, blue)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            temperature: float = kwargs[ATTR_COLOR_TEMP_KELVIN]

            converter: Callable[..., Any] = GOVEE_COORDINATORS_MAPPER.get(
                GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE, lambda x: x
            )

            await self.coordinator.set_temperature(self._device, converter(temperature))
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.turn_off(self._device)
        self.async_write_ha_state()

    @callback
    def _update_callback(self, device: GoveeDevice) -> None:
        self.async_write_ha_state()
