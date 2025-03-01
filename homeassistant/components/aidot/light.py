"""Support for Aidot lights."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AidotDeviceManagerCoordinator, AidotDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Light."""
    device_manager_coordinator: AidotDeviceManagerCoordinator = entry.runtime_data
    coordinators: dict[str, AidotDeviceUpdateCoordinator] = (
        device_manager_coordinator.data
    )

    async_add_entities(
        AidotLight(hass, update_coordinator)
        for update_coordinator in coordinators.values()
    )


class AidotLight(CoordinatorEntity[AidotDeviceUpdateCoordinator], LightEntity):
    """Representation of a Aidot Wi-Fi Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, hass: HomeAssistant, coordinator: AidotDeviceUpdateCoordinator
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self.update_data()
        self._attr_unique_id = coordinator.device_info.dev_id
        self._attr_max_color_temp_kelvin = coordinator.device_info.cct_max
        self._attr_min_color_temp_kelvin = coordinator.device_info.cct_min

        modelId = coordinator.device_info.model_id
        manufacturer = modelId.split(".")[0]
        model = modelId[len(manufacturer) + 1 :]
        mac = format_mac(coordinator.device_info.mac)
        identifiers: set[tuple[str, str]] = set({(DOMAIN, self._attr_unique_id)})

        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=manufacturer,
            model=model,
            name=coordinator.device_info.name,
            hw_version=coordinator.device_info.hw_version,
        )
        if coordinator.device_info.enable_rgbw:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes = {ColorMode.RGBW, ColorMode.COLOR_TEMP}
        elif coordinator.device_info.enable_cct:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def update_data(self) -> None:
        """Update."""
        self._attr_available = self.coordinator.data.online
        self._attr_is_on = self.coordinator.data.on
        self._attr_brightness = self.coordinator.data.dimming
        self._attr_color_temp_kelvin = self.coordinator.data.cct
        self._attr_rgbw_color = self.coordinator.data.rgbw

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.device_client.async_set_brightness(
                kwargs.get(ATTR_BRIGHTNESS, 255)
            )
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            await self.coordinator.device_client.async_set_cct(
                kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            )
        if ATTR_RGBW_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGBW
            await self.coordinator.device_client.async_set_rgbw(
                kwargs.get(ATTR_RGBW_COLOR)
            )
        if not kwargs:
            await self.coordinator.device_client.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.device_client.async_turn_off()

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self.update_data()
        self.async_write_ha_state()
