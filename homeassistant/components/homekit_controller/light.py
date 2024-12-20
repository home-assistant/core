"""Support for Homekit lights."""

from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes
from propcache import cached_property

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit lightbulb."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.LIGHTBULB:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity = HomeKitLight(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.LIGHT
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)


class HomeKitLight(HomeKitEntity, LightEntity):
    """Representation of a Homekit light."""

    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    @callback
    def _async_reconfigure(self) -> None:
        """Reconfigure entity."""
        self._async_clear_property_cache(
            (
                "supported_features",
                "min_color_temp_kelvin",
                "max_color_temp_kelvin",
                "supported_color_modes",
            )
        )
        super()._async_reconfigure()

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ON,
            CharacteristicsTypes.BRIGHTNESS,
            CharacteristicsTypes.COLOR_TEMPERATURE,
            CharacteristicsTypes.HUE,
            CharacteristicsTypes.SATURATION,
        ]

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.service.value(CharacteristicsTypes.ON)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self.service.value(CharacteristicsTypes.BRIGHTNESS) * 255 / 100

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the color property."""
        return (
            self.service.value(CharacteristicsTypes.HUE),
            self.service.value(CharacteristicsTypes.SATURATION),
        )

    @cached_property
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        if not self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
            return DEFAULT_MAX_KELVIN
        min_value_mireds = self.service[CharacteristicsTypes.COLOR_TEMPERATURE].minValue
        return (
            color_util.color_temperature_mired_to_kelvin(min_value_mireds)
            if min_value_mireds
            else DEFAULT_MAX_KELVIN
        )

    @cached_property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        if not self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
            return DEFAULT_MIN_KELVIN
        max_value_mireds = self.service[CharacteristicsTypes.COLOR_TEMPERATURE].maxValue
        return (
            color_util.color_temperature_mired_to_kelvin(max_value_mireds)
            if max_value_mireds
            else DEFAULT_MIN_KELVIN
        )

    @property
    def color_temp_kelvin(self) -> int:
        """Return the color temperature value in Kelvin."""
        return color_util.color_temperature_mired_to_kelvin(
            self.service.value(CharacteristicsTypes.COLOR_TEMPERATURE)
        )

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        # aiohomekit does not keep track of the light's color mode, report
        # hs for light supporting both hs and ct
        if self.service.has(CharacteristicsTypes.HUE) or self.service.has(
            CharacteristicsTypes.SATURATION
        ):
            return ColorMode.HS

        if self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
            return ColorMode.COLOR_TEMP

        if self.service.has(CharacteristicsTypes.BRIGHTNESS):
            return ColorMode.BRIGHTNESS

        return ColorMode.ONOFF

    @cached_property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        color_modes: set[ColorMode] = set()

        if self.service.has(CharacteristicsTypes.HUE) or self.service.has(
            CharacteristicsTypes.SATURATION
        ):
            color_modes.add(ColorMode.HS)
            color_modes.add(ColorMode.COLOR_TEMP)

        elif self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
            color_modes.add(ColorMode.COLOR_TEMP)

        if not color_modes and self.service.has(CharacteristicsTypes.BRIGHTNESS):
            color_modes.add(ColorMode.BRIGHTNESS)

        if not color_modes:
            color_modes.add(ColorMode.ONOFF)

        return color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the specified light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR)
        temperature_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        characteristics: dict[str, Any] = {}

        if brightness is not None:
            characteristics[CharacteristicsTypes.BRIGHTNESS] = int(
                brightness * 100 / 255
            )

        # If they send both temperature and hs_color, and the device
        # does not support both, temperature will win. This is not
        # expected to happen in the UI, but it is possible via a manual
        # service call.
        if temperature_kelvin is not None:
            if self.service.has(CharacteristicsTypes.COLOR_TEMPERATURE):
                characteristics[CharacteristicsTypes.COLOR_TEMPERATURE] = (
                    color_util.color_temperature_kelvin_to_mired(temperature_kelvin)
                )

            elif hs_color is None:
                # Some HomeKit devices implement color temperature with HS
                # since the spec "technically" does not permit the COLOR_TEMPERATURE
                # characteristic and the HUE and SATURATION characteristics to be
                # present at the same time.
                hue_sat = color_util.color_temperature_to_hs(temperature_kelvin)
                characteristics[CharacteristicsTypes.HUE] = hue_sat[0]
                characteristics[CharacteristicsTypes.SATURATION] = hue_sat[1]

        if hs_color is not None:
            characteristics[CharacteristicsTypes.HUE] = hs_color[0]
            characteristics[CharacteristicsTypes.SATURATION] = hs_color[1]

        characteristics[CharacteristicsTypes.ON] = True

        await self.async_put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified light off."""
        await self.async_put_characteristics({CharacteristicsTypes.ON: False})
