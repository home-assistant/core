"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from propcache.api import cached_property
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dali Center light entities from config entry."""
    runtime_data = entry.runtime_data
    gateway = runtime_data.gateway
    devices = [Device(gateway, device) for device in runtime_data.device_data_list]

    def _on_light_status(dev_id: str, status: LightStatus) -> None:
        signal = f"dali_center_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, status)

    gateway.on_light_status = _on_light_status

    _LOGGER.debug("Setting up light platform: %d devices", len(devices))

    added_entities: set[str] = set()
    new_lights: list[DaliCenterLight] = []
    for device in devices:
        if device.dev_id in added_entities:
            continue
        if is_light_device(device.dev_type):
            new_lights.append(DaliCenterLight(device))
            added_entities.add(device.dev_id)

    if new_lights:
        async_add_entities(new_lights)


class DaliCenterLight(LightEntity):
    """Representation of a Dali Center Light."""

    _attr_has_entity_name = True

    def __init__(self, light: Device) -> None:
        """Initialize the light entity."""

        self._light = light
        self._attr_name = None
        self._attr_unique_id = light.unique_id
        self._attr_available = light.status == "online"
        self._attr_is_on: bool | None = None
        self._attr_brightness: int | None = None
        self._white_level: int | None = None
        self._attr_color_mode: ColorMode | str | None = None
        self._attr_color_temp_kelvin: int | None = None
        self._attr_hs_color: tuple[float, float] | None = None
        self._attr_rgbw_color: tuple[int, int, int, int] | None = None
        self._determine_features()

    def _determine_features(self) -> None:
        supported_modes: set[ColorMode] = set()
        color_mode = self._light.color_mode
        if color_mode == "color_temp":
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif color_mode == "hs":
            self._attr_color_mode = ColorMode.HS
        elif color_mode == "rgbw":
            self._attr_color_mode = ColorMode.RGBW
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        supported_modes.add(self._attr_color_mode)
        self._attr_supported_color_modes = supported_modes

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._light.dev_id)},
            name=self._light.name,
            manufacturer=MANUFACTURER,
            model=self._light.model,
            via_device=(DOMAIN, self._light.gw_sn),
        )

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum color temperature in Kelvin."""
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum color temperature in Kelvin."""
        return 8000

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
        del kwargs  # Unused parameter
        self._light.turn_off()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""

        # Handle device-specific updates
        signal = f"dali_center_update_{self._attr_unique_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._handle_device_update)
        )

        self._light.read_status()

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
