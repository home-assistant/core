"""Light for Midea."""

from dataclasses import dataclass
from typing import Any, cast, override

from midealocal.const import DeviceType
from midealocal.devices.x13 import Midea13Device

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaLightEntityDescription(LightEntityDescription):
    """Description for a Midea light entity."""

    models: list[DeviceType]


LIGHTS: list[MideaLightEntityDescription] = [
    MideaLightEntityDescription(
        key="light",
        models=[DeviceType.X13],
        translation_key="light",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaLight(cast(Midea13Device, device), description)
        for description in LIGHTS
        if device.device_type in description.models
    )


class MideaLight(MideaEntity, LightEntity):
    """Represent a Midea light."""

    _device: Midea13Device

    @property
    @override
    def supported_features(self) -> LightEntityFeature:
        """Midea light supported features."""
        if self._device.get_attribute("effect") is not None:
            return LightEntityFeature.EFFECT
        return LightEntityFeature(0)

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Midea light supported color modes."""
        if self._device.get_attribute("color_temperature") is not None:
            return {ColorMode.COLOR_TEMP}
        if self._device.get_attribute("brightness") is not None:
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Midea light current color mode."""
        supported = self.supported_color_modes
        if ColorMode.COLOR_TEMP in supported and self.color_temp_kelvin is not None:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in supported and self.brightness is not None:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    @override
    def is_on(self) -> bool | None:
        """Midea light is on."""
        power = self._device.get_attribute("power")
        if not isinstance(power, bool):
            return None
        return power

    @property
    @override
    def brightness(self) -> int | None:
        """Midea light brightness."""
        value = self._device.get_attribute("brightness")
        return value if isinstance(value, int) else None

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Midea light color temperature."""
        value = self._device.get_attribute("color_temperature")
        return value if isinstance(value, int) else None

    @property
    @override
    def min_color_temp_kelvin(self) -> int:
        """Midea light min color temperature."""
        return self._device.color_temp_range[0]

    @property
    @override
    def max_color_temp_kelvin(self) -> int:
        """Midea light max color temperature."""
        return self._device.color_temp_range[1]

    @property
    @override
    def effect_list(self) -> list[str]:
        """Midea light effect list."""
        return [EFFECT_OFF if e == "none" else e for e in self._device.effects]

    @property
    @override
    def effect(self) -> str | None:
        """Midea light current effect."""
        value = self._device.get_attribute("effect")
        if not isinstance(value, str):
            return None
        return EFFECT_OFF if value == "none" else value

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea light turn on."""
        with midea_api_call():
            if not self.is_on:
                self._device.set_attribute(attr="power", value=True)
            if ATTR_BRIGHTNESS in kwargs:
                self._device.set_attribute(
                    attr="brightness", value=kwargs[ATTR_BRIGHTNESS]
                )
            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                self._device.set_attribute(
                    attr="color_temperature", value=kwargs[ATTR_COLOR_TEMP_KELVIN]
                )
            if ATTR_EFFECT in kwargs:
                effect = kwargs[ATTR_EFFECT]
                self._device.set_attribute(
                    attr="effect",
                    value="none" if effect == EFFECT_OFF else effect,
                )

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea light turn off."""
        with midea_api_call():
            self._device.set_attribute(attr="power", value=False)
