"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import Device
from PySrDaliGateway.helper import is_light_device
from PySrDaliGateway.types import LightStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DALI Center light entities from config entry."""
    runtime_data = entry.runtime_data
    gateway = runtime_data.gateway
    devices = runtime_data.devices

    def _on_light_status(dev_id: str, status: LightStatus) -> None:
        signal = f"{DOMAIN}_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, status)

    gateway.on_light_status = _on_light_status

    new_lights = [
        DaliCenterLight(device)
        for device in devices
        if is_light_device(device.dev_type)
    ]
    async_add_entities(new_lights)


class DaliCenterLight(LightEntity):
    """Representation of a DALI Center Light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _white_level: int | None = None
    _attr_color_mode: ColorMode | str | None = None
    _attr_color_temp_kelvin: int | None = None
    _attr_hs_color: tuple[float, float] | None = None
    _attr_rgbw_color: tuple[int, int, int, int] | None = None

    def __init__(self, light: Device) -> None:
        """Initialize the light entity."""

        self._light = light
        self._unavailable_logged = False
        self._attr_unique_id = light.unique_id
        self._attr_available = light.status == "online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, light.dev_id)},
            name=light.name,
            manufacturer=MANUFACTURER,
            model=light.model,
            via_device=(DOMAIN, light.gw_sn),
        )
        self._attr_min_color_temp_kelvin = 1000
        self._attr_max_color_temp_kelvin = 8000

        self._determine_features()

    def _determine_features(self) -> None:
        supported_modes: set[ColorMode] = set()
        color_mode = self._light.color_mode
        color_mode_map: dict[str, ColorMode] = {
            "color_temp": ColorMode.COLOR_TEMP,
            "hs": ColorMode.HS,
            "rgbw": ColorMode.RGBW,
        }
        self._attr_color_mode = color_mode_map.get(color_mode, ColorMode.BRIGHTNESS)
        supported_modes.add(self._attr_color_mode)
        self._attr_supported_color_modes = supported_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        _LOGGER.debug(
            "Turning on light %s with kwargs: %s", self._attr_unique_id, kwargs
        )
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
        self._light.turn_on(
            brightness=brightness,
            color_temp_kelvin=color_temp_kelvin,
            hs_color=hs_color,
            rgbw_color=rgbw_color,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._light.turn_off()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        signal = f"{DOMAIN}_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        signal = f"{DOMAIN}_update_available_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_availability)
        )

        self._light.read_status()

    @callback
    def _handle_availability(self, available: bool) -> None:
        self._attr_available = available
        if not available and not self._unavailable_logged:
            _LOGGER.info("Light %s became unavailable", self._attr_unique_id)
            self._unavailable_logged = True
        elif available and self._unavailable_logged:
            _LOGGER.info("Light %s is back online", self._attr_unique_id)
            self._unavailable_logged = False
        self.schedule_update_ha_state()

    @callback
    def _handle_device_update(self, status: LightStatus) -> None:
        if status.get("is_on") is not None:
            self._attr_is_on = status["is_on"]

        if status.get("brightness") is not None:
            self._attr_brightness = status["brightness"]

        if status.get("white_level") is not None:
            self._white_level = status["white_level"]
            if self._attr_rgbw_color is not None and self._white_level is not None:
                self._attr_rgbw_color = (
                    self._attr_rgbw_color[0],
                    self._attr_rgbw_color[1],
                    self._attr_rgbw_color[2],
                    self._white_level,
                )

        if (
            status.get("color_temp_kelvin") is not None
            and self._attr_supported_color_modes
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            self._attr_color_temp_kelvin = status["color_temp_kelvin"]

        if (
            status.get("hs_color") is not None
            and self._attr_supported_color_modes
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            self._attr_hs_color = status["hs_color"]

        if (
            status.get("rgbw_color") is not None
            and self._attr_supported_color_modes
            and ColorMode.RGBW in self._attr_supported_color_modes
        ):
            self._attr_rgbw_color = status["rgbw_color"]

        self.async_write_ha_state()
