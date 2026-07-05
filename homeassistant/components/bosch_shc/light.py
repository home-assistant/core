"""Platform for light integration."""

from typing import Any, NoReturn, override

from boschshcpy import SHCLight, SHCMicromoduleDimmer
from boschshcpy.device import SHCDevice
from boschshcpy.exceptions import SHCException
from boschshcpy.services_impl import PowerSwitchService
from requests.exceptions import RequestException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 1


def _raise_write_error(
    device: SHCDevice, translation_key: str, err: SHCException | RequestException
) -> NoReturn:
    """Convert a boschshcpy device-write failure into a translated HomeAssistantError."""
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={"name": device.name, "error": str(err)},
    ) from err


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
        for device in (
            *session.device_helper.hue_lights,
            *session.device_helper.ledvance_lights,
            *session.device_helper.micromodule_dimmers,
        )
    )

    async_add_entities(entities)


class SHCOnOffLight(SHCEntity, LightEntity):
    """Representation of a SHC on/off-only light switch (micromodule light attached)."""

    _attr_name = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    @override
    def is_on(self) -> bool:
        """Return true when the switch is on."""
        return self._device.switchstate == PowerSwitchService.State.ON

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            self._device.switchstate = True
        except (SHCException, RequestException) as err:
            _raise_write_error(self._device, "light_turn_on_failed", err)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            self._device.switchstate = False
        except (SHCException, RequestException) as err:
            _raise_write_error(self._device, "light_turn_off_failed", err)


class SHCColorLight(SHCEntity, LightEntity):
    """Representation of a SHC dimmable/colour light (Hue, Ledvance, Dimmer).

    Maps Bosch capabilities onto HA color modes:
      HSBColorActuator (implies HueColorTemperature too) → ColorMode.HS + ColorMode.COLOR_TEMP
      HueColorTemperature only (no HSB) → ColorMode.COLOR_TEMP
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
        modes: set[ColorMode] = set()
        if device.supports_color_hsb:
            modes.add(ColorMode.HS)
            modes.add(ColorMode.COLOR_TEMP)
        elif device.supports_color_temp:
            modes.add(ColorMode.COLOR_TEMP)
        elif device.supports_brightness:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)
        self._attr_supported_color_modes = modes
        # boschshcpy doesn't clear rgb when a color temperature is written (and
        # vice versa), so the active mode can't be inferred from device state
        # alone; track the mode we last wrote instead.
        if device.supports_color_hsb:
            self._attr_color_mode = ColorMode.HS if device.rgb else ColorMode.COLOR_TEMP
        elif device.supports_color_temp:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif device.supports_brightness:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

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
        """Return colour temperature in Kelvin, converted from Bosch's mireds."""
        if not self._device.supports_color_temp and not self._device.supports_color_hsb:
            return None
        if not self._device.color:
            return None
        return color_temperature_mired_to_kelvin(self._device.color)

    @property
    @override
    def min_color_temp_kelvin(self) -> int:
        """Return minimum colour temperature (warmest) in Kelvin.

        Mireds and Kelvin are inversely related, so the largest mired value
        (the device's max_color_temperature) is the smallest Kelvin value.
        """
        max_ct = self._device.max_color_temperature
        if not max_ct:
            return 2700
        return color_temperature_mired_to_kelvin(max_ct)

    @property
    @override
    def max_color_temp_kelvin(self) -> int:
        """Return maximum colour temperature (coolest) in Kelvin.

        Mireds and Kelvin are inversely related, so the smallest mired value
        (the device's min_color_temperature) is the largest Kelvin value.
        """
        min_ct = self._device.min_color_temperature
        if not min_ct:
            return 6500
        return color_temperature_mired_to_kelvin(min_ct)

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
            try:
                self._device.binarystate = True
            except (SHCException, RequestException) as err:
                _raise_write_error(self._device, "light_turn_on_failed", err)

        if ATTR_BRIGHTNESS in kwargs and self._device.supports_brightness:
            # Convert HA 0-255 → Bosch 0-100, clamped to a minimum of 1: HA's
            # lowest turn-on brightness is 1, and round(1 * 100 / 255) is 0,
            # which is the Bosch "off" value.
            brightness = max(round(kwargs[ATTR_BRIGHTNESS] * 100 / 255), 1)
            try:
                self._device.brightness = brightness
            except (SHCException, RequestException) as err:
                _raise_write_error(self._device, "light_turn_on_failed", err)

        if ATTR_COLOR_TEMP_KELVIN in kwargs and (
            self._device.supports_color_temp or self._device.supports_color_hsb
        ):
            mireds = color_temperature_kelvin_to_mired(kwargs[ATTR_COLOR_TEMP_KELVIN])
            try:
                self._device.color = mireds
            except (SHCException, RequestException) as err:
                _raise_write_error(self._device, "light_turn_on_failed", err)
            self._attr_color_mode = ColorMode.COLOR_TEMP

        if ATTR_HS_COLOR in kwargs and self._device.supports_color_hsb:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            red, green, blue = color_hs_to_RGB(hue, saturation)
            try:
                self._device.rgb = (red << 16) | (green << 8) | blue
            except (SHCException, RequestException) as err:
                _raise_write_error(self._device, "light_turn_on_failed", err)
            self._attr_color_mode = ColorMode.HS

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            self._device.binarystate = False
        except (SHCException, RequestException) as err:
            _raise_write_error(self._device, "light_turn_off_failed", err)
