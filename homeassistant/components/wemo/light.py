"""Support for Belkin WeMo lights."""

from __future__ import annotations

from typing import Any, cast

from pywemo import Bridge, BridgeLight, Dimmer

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from . import async_wemo_dispatcher_connect
from .const import DOMAIN as WEMO_DOMAIN
from .coordinator import DeviceCoordinator
from .entity import WemoBinaryStateEntity, WemoEntity

# The WEMO_ constants below come from pywemo itself
WEMO_OFF = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WeMo lights."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        if isinstance(coordinator.wemo, Bridge):
            async_setup_bridge(hass, config_entry, async_add_entities, coordinator)
        else:
            async_add_entities([WemoDimmer(coordinator)])

    await async_wemo_dispatcher_connect(hass, _discovered_wemo)


@callback
def async_setup_bridge(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: DeviceCoordinator,
) -> None:
    """Set up a WeMo link."""
    known_light_ids = set()

    @callback
    def async_update_lights() -> None:
        """Check to see if the bridge has any new lights."""
        new_lights = []

        bridge = cast(Bridge, coordinator.wemo)
        for light_id, light in bridge.Lights.items():
            if light_id not in known_light_ids:
                known_light_ids.add(light_id)
                new_lights.append(WemoLight(coordinator, light))

        async_add_entities(new_lights)

    async_update_lights()
    config_entry.async_on_unload(coordinator.async_add_listener(async_update_lights))


class WemoLight(WemoEntity, LightEntity):
    """Representation of a WeMo light."""

    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(self, coordinator: DeviceCoordinator, light: BridgeLight) -> None:
        """Initialize the WeMo light."""
        super().__init__(coordinator)
        self.light = light
        self._unique_id = self.light.uniqueID
        self._model_name = type(self.light).__name__

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.light.name

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        return super().available and self.light.state.get("available", False)

    @property
    def unique_id(self) -> str:
        """Return the ID of this light."""
        return self.light.uniqueID

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, self._unique_id)},
            identifiers={(WEMO_DOMAIN, self._unique_id)},
            manufacturer="Belkin",
            model=self._model_name,
            name=self.name,
        )

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self.light.state.get("level", 255)

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self.light.state.get("color_xy")

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
        if not (mireds := self.light.state.get("temperature_mireds")):
            return None
        return color_util.color_temperature_mired_to_kelvin(mireds)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if (
            "colorcontrol" in self.light.capabilities
            and self.light.state.get("color_xy") is not None
        ):
            return ColorMode.XY
        if "colortemperature" in self.light.capabilities:
            return ColorMode.COLOR_TEMP
        if "levelcontrol" in self.light.capabilities:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        modes: set[ColorMode] = set()
        if "colorcontrol" in self.light.capabilities:
            modes.add(ColorMode.XY)
        if "colortemperature" in self.light.capabilities:
            modes.add(ColorMode.COLOR_TEMP)
        if "levelcontrol" in self.light.capabilities and not modes:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)
        return modes

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.light.state.get("onoff", WEMO_OFF) != WEMO_OFF

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        xy_color = None

        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        transition_time = int(kwargs.get(ATTR_TRANSITION, 0))

        if hs_color is not None:
            xy_color = color_util.color_hs_to_xy(*hs_color)

        turn_on_kwargs = {
            "level": brightness,
            "transition": transition_time,
            "force_update": False,
        }

        with self._wemo_call_wrapper("turn on"):
            if xy_color is not None:
                self.light.set_color(xy_color, transition=transition_time)

            if color_temp_kelvin is not None:
                self.light.set_temperature(
                    kelvin=color_temp_kelvin, transition=transition_time
                )

            self.light.turn_on(**turn_on_kwargs)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        transition_time = int(kwargs.get(ATTR_TRANSITION, 0))

        with self._wemo_call_wrapper("turn off"):
            self.light.turn_off(transition=transition_time)


class WemoDimmer(WemoBinaryStateEntity, LightEntity):
    """Representation of a WeMo dimmer."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    wemo: Dimmer

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 1 and 100."""
        wemo_brightness: int = self.wemo.get_brightness()
        return int((wemo_brightness * 255) / 100)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on."""
        # Wemo dimmer switches use a range of [0, 100] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
            with self._wemo_call_wrapper("set brightness"):
                self.wemo.set_brightness(brightness)
        else:
            with self._wemo_call_wrapper("turn on"):
                self.wemo.on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmer off."""
        with self._wemo_call_wrapper("turn off"):
            self.wemo.off()
