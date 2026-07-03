"""Platform for light integration."""

from typing import Any, override

from boschshcpy import SHCLight, SHCLightSwitch, SHCMicromoduleDimmer
from boschshcpy.services_impl import PowerSwitchService

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import color_hs_to_RGB, color_RGB_to_hs

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC light platform."""
    session = config_entry.runtime_data

    # light_switches_bsm is intentionally not exposed here: those devices are
    # already created as switch.* entities in switch.py, and adding them here
    # too would control the same physical device from two separate domains.
    entities: list[LightEntity] = [
        SHCOnOffLight(
            device=device,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.micromodule_light_attached
    ]

    entities.extend(
        SHCColorLight(
            device=device,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.hue_lights
    )

    entities.extend(
        SHCColorLight(
            device=device,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.ledvance_lights
    )

    entities.extend(
        SHCColorLight(
            device=device,
            parent_id=session.information.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.micromodule_dimmers
    )

    async_add_entities(entities)


class SHCOnOffLight(SHCEntity, LightEntity):
    """Representation of a SHC on/off-only light switch (micromodule light attached)."""

    _attr_name = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        device: SHCLightSwitch,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize a SHC on/off light."""
        super().__init__(device, parent_id, entry_id)

    @property
    @override
    def is_on(self) -> bool:
        """Return true when the switch is on."""
        return self._device.switchstate == PowerSwitchService.State.ON

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        self._device.switchstate = True

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._device.switchstate = False


class SHCColorLight(SHCEntity, LightEntity):
    """Representation of a SHC dimmable/colour light (Hue, Ledvance, Dimmer).

    Maps Bosch capabilities onto HA color modes:
      HSBColorActuator  → ColorMode.HS
      HueColorTemperature (without HSB) → ColorMode.COLOR_TEMP
      MultiLevelSwitch only → ColorMode.BRIGHTNESS
      none of the above → ColorMode.ONOFF
    """

    _attr_name = None

    def __init__(
        self,
        device: SHCLight | SHCMicromoduleDimmer,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize a SHC colour light."""
        super().__init__(device, parent_id, entry_id)
        # boschshcpy doesn't clear rgb when a color temperature is written (and
        # vice versa), so the active mode can't be inferred from device state
        # alone; track the mode we last wrote instead.
        if device.supports_color_hsb:
            self._color_mode = ColorMode.HS if device.rgb else ColorMode.COLOR_TEMP
        elif device.supports_color_temp:
            self._color_mode = ColorMode.COLOR_TEMP
        elif device.supports_brightness:
            self._color_mode = ColorMode.BRIGHTNESS
        else:
            self._color_mode = ColorMode.ONOFF

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes based on device capabilities."""
        modes: set[ColorMode] = set()
        if self._device.supports_color_hsb:
            modes.add(ColorMode.HS)
            modes.add(ColorMode.COLOR_TEMP)
        elif self._device.supports_color_temp:
            modes.add(ColorMode.COLOR_TEMP)
        elif self._device.supports_brightness:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)
        return modes

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the active color mode."""
        return self._color_mode

    @property
    @override
    def is_on(self) -> bool:
        """Return true when the light is on."""
        return bool(self._device.binarystate)

    @property
    @override
    def brightness(self) -> int | None:
        """Return brightness (0-255) converted from Bosch 0-100 scale."""
        if not self._device.supports_brightness:
            return None
        return round(self._device.brightness * 255 / 100)

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return colour temperature in Kelvin (Bosch stores Kelvin directly)."""
        if not self._device.supports_color_temp and not self._device.supports_color_hsb:
            return None
        value = self._device.color
        return value or None

    @property
    @override
    def min_color_temp_kelvin(self) -> int:
        """Return minimum colour temperature (warmest) in Kelvin."""
        return self._device.min_color_temperature or 2700

    @property
    @override
    def max_color_temp_kelvin(self) -> int:
        """Return maximum colour temperature (coolest) in Kelvin."""
        return self._device.max_color_temperature or 6500

    @property
    @override
    def hs_color(self) -> tuple[float, float] | None:
        """Return hue/saturation from the packed RGB integer."""
        if not self._device.supports_color_hsb:
            return None
        rgb_int = self._device.rgb
        if not rgb_int:
            return None
        red = (rgb_int >> 16) & 0xFF
        green = (rgb_int >> 8) & 0xFF
        blue = rgb_int & 0xFF
        return color_RGB_to_hs(red, green, blue)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally setting brightness / colour."""
        if not self.is_on:
            self._device.binarystate = True

        if ATTR_BRIGHTNESS in kwargs and self._device.supports_brightness:
            # Convert HA 0-255 → Bosch 0-100
            self._device.brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)

        if ATTR_COLOR_TEMP_KELVIN in kwargs and (
            self._device.supports_color_temp or self._device.supports_color_hsb
        ):
            self._device.color = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._color_mode = ColorMode.COLOR_TEMP

        if ATTR_HS_COLOR in kwargs and self._device.supports_color_hsb:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            red, green, blue = color_hs_to_RGB(hue, saturation)
            self._device.rgb = (red << 16) | (green << 8) | blue
            self._color_mode = ColorMode.HS

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._device.binarystate = False
