"""Platform for light integration."""

from boschshcpy import SHCSession
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import Platform
from homeassistant.util import color as color_util

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity, async_migrate_to_new_unique_id, device_excluded

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the light platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for light in (
        session.device_helper.ledvance_lights
        + session.device_helper.micromodule_dimmers
        + session.device_helper.hue_lights
    ):
        if device_excluded(light, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(hass, Platform.LIGHT, device=light)
        entities.append(
            LightSwitch(
                device=light,
                entry_id=config_entry.entry_id,
            )
        )

    for light in session.device_helper.motion_detectors2:
        if device_excluded(light, config_entry.options):
            continue
        await async_migrate_to_new_unique_id(
            hass, Platform.LIGHT, device=light, attr_name="MotionLight"
        )
        entities.append(
            MotionDetectorLight(
                device=light,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class LightSwitch(SHCEntity, LightEntity):
    """Representation of a SHC controlled light."""

    def __init__(self, device, entry_id) -> None:
        super().__init__(device=device, entry_id=entry_id)
        self._attr_supported_color_modes: set[ColorMode] = set()

        if self._device.supports_color_hsb:
            self._attr_supported_color_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS
        if self._device.supports_color_temp:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            # Only set COLOR_TEMP as default when HS is NOT also supported;
            # when both are present, HS takes priority (set above).
            if not self._device.supports_color_hsb:
                self._attr_color_mode = ColorMode.COLOR_TEMP
        if self._device.supports_color_hsb or self._device.supports_color_temp:
            min_ct = self._device.min_color_temperature
            max_ct = self._device.max_color_temperature
            if min_ct and max_ct:
                self._attr_min_color_temp_kelvin = (
                    color_util.color_temperature_mired_to_kelvin(min_ct)
                )
                self._attr_max_color_temp_kelvin = (
                    color_util.color_temperature_mired_to_kelvin(max_ct)
                )
        if self._device.supports_brightness:
            if (
                len(self._attr_supported_color_modes) == 0
            ):  # BRIGHTNESS must be the only supported mode
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            if (
                len(self._attr_supported_color_modes) == 0
            ):  # ONOFF must be the only supported mode
                self._attr_supported_color_modes.add(ColorMode.ONOFF)
                self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self):
        """Return light state."""
        return self._device.binarystate

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        raw = self._device.brightness
        if raw is None:
            return None
        return round(raw * 255 / 100)

    @property
    def hs_color(self):
        """Return the rgb color of this light."""
        rgb_raw = self._device.rgb
        rgb = ((rgb_raw >> 16) & 0xFF, (rgb_raw >> 8) & 0xFF, rgb_raw & 0xFF)
        return color_util.color_RGB_to_hs(*rgb)

    @property
    def color_temp_kelvin(self):
        """Return the color temp of this light."""
        if not self._device.color:
            return None
        return color_util.color_temperature_mired_to_kelvin(self._device.color)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None and self._device.supports_brightness:
            # Bosch API does not accept brightness=0; HA uses brightness=0 to
            # mean "off", which is handled via binarystate. Clamp to 1 so that
            # a near-zero HA value (e.g. 1/255) never silently turns off.
            await self._device.async_set_brightness(
                max(round(brightness * 100 / 255), 1)
            )

        if color_temp_kelvin is not None and self._device.supports_color_temp:
            await self._device.async_set_color(
                color_util.color_temperature_kelvin_to_mired(color_temp_kelvin)
            )
            self._attr_color_mode = ColorMode.COLOR_TEMP

        if hs_color is not None and self._device.supports_color_hsb:
            rgb = color_util.color_hs_to_RGB(*hs_color)
            raw_rgb = (rgb[0] << 16) + (rgb[1] << 8) + rgb[2]
            await self._device.async_set_rgb(raw_rgb)
            self._attr_color_mode = ColorMode.HS

        if not self.is_on:
            await self._device.async_set_binarystate(True)

        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._device.async_set_binarystate(False)


class MotionDetectorLight(SHCEntity, LightEntity):
    """Representation of the indicator light on a SHC Motion Detector II [+M]."""

    _attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, device, entry_id: str) -> None:
        """Initialize the Motion Detector II light entity."""
        super().__init__(device=device, entry_id=entry_id)
        self._attr_name = "Motion Light"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_motionlight"
        )

    @property
    def is_on(self) -> bool:
        """Return the current on/off state."""
        return self._device.binaryswitch

    @property
    def brightness(self) -> int:
        """Return the brightness scaled to 0-255."""
        level = self._device.multi_level_switch
        if level is None:
            return 0
        return round(level * 255 / 100)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on, optionally setting brightness."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            # Clamp to 1 so near-zero HA values don't silently turn the light off.
            level = max(round(brightness * 100 / 255), 1)
            await self._device.async_set_multi_level_switch(level)
        if not self.is_on:
            await self._device.async_set_binaryswitch(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        await self._device.async_set_binaryswitch(False)
