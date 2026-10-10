"""Support for Aidot lights."""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AidotConfigEntry, AidotDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AidotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Light."""
    coordinator = entry.runtime_data
    async_add_entities(
        AidotLight(device_coordinator)
        for device_coordinator in coordinator.device_coordinators.values()
    )


class AidotLight(CoordinatorEntity[AidotDeviceUpdateCoordinator], LightEntity):
    """Representation of a Aidot Wi-Fi Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: AidotDeviceUpdateCoordinator) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device_client.info.dev_id
        if hasattr(coordinator.device_client.info, "cct_max"):
            self._attr_max_color_temp_kelvin = coordinator.device_client.info.cct_max
        if hasattr(coordinator.device_client.info, "cct_min"):
            self._attr_min_color_temp_kelvin = coordinator.device_client.info.cct_min

        model_id = coordinator.device_client.info.model_id
        manufacturer = model_id.split(".")[0]
        model = model_id[len(manufacturer) + 1 :]
        mac = coordinator.device_client.info.mac

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=manufacturer,
            model=model,
            name=coordinator.device_client.info.name,
            hw_version=coordinator.device_client.info.hw_version,
        )
        if coordinator.device_client.info.preset_names:
            self._attr_effect_list = coordinator.device_client.info.preset_names
            self._attr_supported_features = LightEntityFeature.EFFECT
        if coordinator.device_client.info.enable_rgbw:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes = {ColorMode.RGBW, ColorMode.COLOR_TEMP}
        elif coordinator.device_client.info.enable_cct:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._update_status()

    def _update_status(self) -> None:
        """Update light status from coordinator data."""
        self._attr_is_on = self.coordinator.data.on
        self._attr_brightness = self.coordinator.data.dimming
        self._attr_color_temp_kelvin = self.coordinator.data.cct
        self._attr_rgbw_color = self.coordinator.data.rgbw
        self._attr_effect = self.coordinator.data.effect or None

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.online

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update."""
        self._update_status()
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, applying any requested brightness and color."""
        # Brightness is independent of color: a scene sends both at once, and
        # the color must not be dropped just because brightness came with it.
        handled_command = False
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
            await self.coordinator.device_client.async_set_brightness(brightness)
            self.coordinator.data.dimming = brightness
            self._attr_brightness = brightness
            handled_command = True

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            await self.coordinator.device_client.async_set_cct(color_temp_kelvin)
            self.coordinator.data.cct = color_temp_kelvin
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self.coordinator.data.effect = ""
            self._attr_effect = None
            handled_command = True

        if ATTR_RGBW_COLOR in kwargs:
            rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
            await self.coordinator.device_client.async_set_rgbw(rgbw_color)
            self.coordinator.data.rgbw = rgbw_color
            self._attr_rgbw_color = rgbw_color
            self._attr_color_mode = ColorMode.RGBW
            self.coordinator.data.effect = ""
            self._attr_effect = None
            handled_command = True

        if ATTR_EFFECT in kwargs:
            effect = kwargs.get(ATTR_EFFECT)
            await self.coordinator.device_client.async_set_effect(effect)
            self.coordinator.data.effect = effect
            self._attr_effect = effect
            handled_command = True

        if not handled_command:
            # Nothing was requested to apply, so just switch it on.
            await self.coordinator.device_client.async_turn_on()

        self.coordinator.data.on = True
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.device_client.async_turn_off()
        self.coordinator.data.on = False
        self._attr_is_on = False
        self.async_write_ha_state()
