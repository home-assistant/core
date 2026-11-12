"""Light platform for Trimlight controllers."""

from typing import Any, override

from aiotrimlight import TrimlightICType, TrimlightLightState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DID, DOMAIN
from .coordinator import TrimlightConfigEntry, TrimlightCoordinator

PARALLEL_UPDATES = 0

IC_COLOR_MODES = {
    TrimlightICType.RGB: ColorMode.RGB,
    TrimlightICType.RGBW: ColorMode.RGBW,
    TrimlightICType.RGBCW: ColorMode.RGBWW,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrimlightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one light for a Trimlight controller."""
    async_add_entities([TrimlightLight(entry)])


class TrimlightLight(CoordinatorEntity[TrimlightCoordinator], LightEntity):
    """Representation of a Trimlight controller."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: TrimlightConfigEntry) -> None:
        """Initialize the Trimlight light."""
        coordinator = entry.runtime_data
        super().__init__(coordinator)
        did = entry.data[CONF_DID]
        self._attr_unique_id = did
        self._attr_device_info = DeviceInfo(
            model="Trimlight Edge Pro",
            connections={(CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])},
            identifiers={(DOMAIN, did)},
            manufacturer="Trimlight",
            name=entry.title,
            sw_version=coordinator.device_info.firmware_version,
        )
        self._color_mode = IC_COLOR_MODES[coordinator.device_info.ic_type]
        self._attr_supported_color_modes = {self._color_mode}
        self._apply_state(coordinator.data)

    def _apply_state(self, state: TrimlightLightState) -> None:
        """Apply cached coordinator state."""
        self._attr_is_on = state.is_on
        self._attr_brightness = state.brightness
        red = state.red
        green = state.green
        blue = state.blue
        self._attr_color_mode = ColorMode.UNKNOWN

        if self._color_mode is ColorMode.RGB:
            if red is None or green is None or blue is None:
                self._attr_rgb_color = None
                return
            self._attr_rgb_color = (red, green, blue)

        elif self._color_mode is ColorMode.RGBW:
            warm_white = state.warm_white
            if red is None or green is None or blue is None or warm_white is None:
                self._attr_rgbw_color = None
                return
            self._attr_rgbw_color = (red, green, blue, warm_white)

        else:
            warm_white = state.warm_white
            cold_white = state.cold_white
            if (
                red is None
                or green is None
                or blue is None
                or warm_white is None
                or cold_white is None
            ):
                self._attr_rgbww_color = None
                return
            self._attr_rgbww_color = (red, green, blue, cold_white, warm_white)

        self._attr_color_mode = self._color_mode

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Apply a runtime state update from the coordinator."""
        self._apply_state(self.coordinator.data)
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        red: int | None = None
        green: int | None = None
        blue: int | None = None
        warm_white: int | None = None
        cold_white: int | None = None

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
        elif ATTR_RGBW_COLOR in kwargs:
            red, green, blue, warm_white = kwargs[ATTR_RGBW_COLOR]
        elif ATTR_RGBWW_COLOR in kwargs:
            red, green, blue, cold_white, warm_white = kwargs[ATTR_RGBWW_COLOR]

        await self.coordinator.async_set_state(
            on=True,
            brightness=kwargs.get(ATTR_BRIGHTNESS),
            red=red,
            green=green,
            blue=blue,
            warm_white=warm_white,
            cold_white=cold_white,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.async_set_state(on=False)
