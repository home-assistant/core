"""Support for Aidot lights."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
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
        mac = format_mac(coordinator.device_client.info.mac)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=manufacturer,
            model=model,
            name=coordinator.device_client.info.name,
            hw_version=coordinator.device_client.info.hw_version,
        )
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
        self._attr_available = self.coordinator.data.online
        self._attr_is_on = self.coordinator.data.on
        self._attr_brightness = self.coordinator.data.dimming
        self._attr_color_temp_kelvin = self.coordinator.data.cct
        self._attr_rgbw_color = self.coordinator.data.rgbw

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.online

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update."""
        self._update_status()
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Fix brightness state synchronization by updating the coordinator's `dimming` field."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
            await self.coordinator.device_client.async_set_brightness(brightness)
            self.coordinator.data.dimming = brightness
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            await self.coordinator.device_client.async_set_cct(color_temp_kelvin)
            self.coordinator.data.cct = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ATTR_RGBW_COLOR in kwargs:
            rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
            await self.coordinator.device_client.async_set_rgbw(rgbw_color)
            self.coordinator.data.rgbw = rgbw_color
            self._attr_color_mode = ColorMode.RGBW
        else:
            await self.coordinator.device_client.async_turn_on()

        self.coordinator.data.on = True
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.device_client.async_turn_off()
        self.coordinator.data.on = False
        self._attr_is_on = False
