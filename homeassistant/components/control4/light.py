"""Platform for Control4 Lights."""

import json
import logging
from typing import Any

from pyControl4.light import C4Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import Control4Entity, get_items_of_category
from .const import CONF_DIRECTOR, CONTROL4_ENTITY_TYPE, Control4ConfigEntry
from .director_utils import director_get_entry_variables

_LOGGER = logging.getLogger(__name__)

CONTROL4_CATEGORY = "lights"
CONTROL4_BRIGHTNESS_SCALE = (1, 100)
CONTROL4_COLOR_MODE_CCT = 1
CONTROL4_COLOR_MODE_XY = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 lights from a config entry."""
    entry_data = entry.runtime_data
    items_of_category = await get_items_of_category(hass, entry, CONTROL4_CATEGORY)

    entity_list = []
    for item in items_of_category:
        try:
            if not (
                item["type"] == CONTROL4_ENTITY_TYPE
                and item["id"]
                and item["proxy"] != "fan"
            ):
                continue
            item_name = str(item["name"])
            item_id = item["id"]
            item_area = item["roomName"]
            item_parent_id = item["parentId"]
            item_manufacturer = None
            item_device_name = None
            item_model = None
            for parent_item in items_of_category:
                if parent_item["id"] == item_parent_id:
                    item_manufacturer = parent_item["manufacturer"]
                    item_device_name = parent_item["name"]
                    item_model = parent_item["model"]
        except KeyError:
            _LOGGER.exception(
                "Unknown device properties received from Control4: %s", item
            )
            continue
        item_attributes = await director_get_entry_variables(hass, entry, item_id)
        entity_list.append(
            Control4Light(
                entry_data,
                entry,
                item_name,
                item_id,
                item_device_name,
                item_manufacturer,
                item_model,
                item_parent_id,
                item_area,
                item_attributes,
            )
        )

    async_add_entities(entity_list, True)


class Control4Light(Control4Entity, LightEntity):
    """Control4 light entity."""

    def __init__(
        self,
        entry_data: dict[str, Any],
        entry: Any,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_parent_id: int,
        device_area: str | None,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(
            entry_data,
            entry,
            name,
            idx,
            device_name,
            device_manufacturer,
            device_model,
            device_parent_id,
            device_area,
            device_attributes,
        )
        self._supports_color: bool = False
        self._supports_ct: bool = False
        self._ct_min: int | None = None
        self._ct_max: int | None = None
        self._rate_min: int | None = None
        self._rate_max: int | None = None
        self._effects_by_name: dict[str, dict[str, Any]] = {}
        self._current_effect: str | None = None
        self._attr_supported_color_modes = (
            {ColorMode.BRIGHTNESS} if self._is_dimmer else {ColorMode.ONOFF}
        )
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if self._is_dimmer else ColorMode.ONOFF
        )
        self._attr_min_color_temp_kelvin = None
        self._attr_max_color_temp_kelvin = None

    def create_api_object(self) -> C4Light:
        """Create a pyControl4 device object with the current director token."""
        return C4Light(self.entry_data[CONF_DIRECTOR], self._idx)

    async def async_added_to_hass(self) -> None:
        """Register websocket callbacks and fetch device setup."""
        await super().async_added_to_hass()
        director = self.entry_data.get(CONF_DIRECTOR)
        if not director:
            return
        try:
            resp = await director.get_item_setup(self._idx)
            setup = resp.get("setup", resp) if isinstance(resp, dict) else {}
            if isinstance(setup, str):
                setup = json.loads(setup)
            self._supports_color = bool(setup.get("supports_color"))
            self._supports_ct = bool(setup.get("supports_color_correlated_temperature"))
            colors = setup.get("colors") or {}
            if self._supports_ct:
                self._ct_min = colors.get("color_correlated_temperature_min") or None
                self._ct_max = colors.get("color_correlated_temperature_max") or None
                if self._ct_min is not None:
                    self._attr_min_color_temp_kelvin = int(self._ct_min)
                if self._ct_max is not None:
                    self._attr_max_color_temp_kelvin = int(self._ct_max)
            self._rate_min = colors.get("color_rate_min")
            self._rate_max = colors.get("color_rate_max")
            for pr in colors.get("color") or []:
                name = pr.get("name")
                if name:
                    self._effects_by_name[name] = pr
            modes: set[ColorMode] = set()
            if self._is_dimmer and not self._supports_color:
                modes.add(ColorMode.BRIGHTNESS)
            if self._supports_color:
                modes.add(ColorMode.XY)
            if self._supports_ct:
                modes.add(ColorMode.COLOR_TEMP)
            if not modes:
                modes = {ColorMode.ONOFF}
            self._attr_supported_color_modes = modes
            if ColorMode.XY in modes:
                self._attr_color_mode = ColorMode.XY
            elif ColorMode.COLOR_TEMP in modes:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            elif ColorMode.BRIGHTNESS in modes:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            else:
                self._attr_color_mode = ColorMode.ONOFF
        except Exception:  # noqa: BLE001
            _LOGGER.debug("get_item_setup failed for %s", self._idx)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return whether this light is on."""
        attrs = self.extra_state_attributes
        if "LIGHT_LEVEL" in attrs:
            return attrs["LIGHT_LEVEL"] > 0
        if "Brightness Percent" in attrs:
            return attrs["Brightness Percent"] > 0
        if "LIGHT_STATE" in attrs:
            return attrs["LIGHT_STATE"] > 0
        if "CURRENT_POWER" in attrs:
            return attrs["CURRENT_POWER"] > 0
        return False

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255)."""
        attrs = self.extra_state_attributes
        if "LIGHT_LEVEL" in attrs:
            return value_to_brightness(CONTROL4_BRIGHTNESS_SCALE, attrs["LIGHT_LEVEL"])
        if "Brightness Percent" in attrs:
            return value_to_brightness(
                CONTROL4_BRIGHTNESS_SCALE, attrs["Brightness Percent"]
            )
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return current color temperature in Kelvin."""
        attrs = self.extra_state_attributes
        mode = attrs.get("light_color_current_color_mode")
        cct = attrs.get("light_color_current_color_correlated_temperature")
        if (
            mode is not None
            and int(mode) == CONTROL4_COLOR_MODE_CCT
            and cct is not None
        ):
            return int(cct)
        return None

    @property
    def min_color_temp_kelvin(self) -> int | None:
        """Return minimum color temperature."""
        return (
            int(self._ct_min)
            if self._ct_min is not None
            else self._attr_min_color_temp_kelvin
        )

    @property
    def max_color_temp_kelvin(self) -> int | None:
        """Return maximum color temperature."""
        return (
            int(self._ct_max)
            if self._ct_max is not None
            else self._attr_max_color_temp_kelvin
        )

    @property
    def effect(self) -> str | None:
        """Return current effect."""
        return self._current_effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return available effects."""
        return sorted(self._effects_by_name) or None

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        features = LightEntityFeature(0)
        if self._is_dimmer or self._supports_color or self._supports_ct:
            features |= LightEntityFeature.TRANSITION
        if self._effects_by_name:
            features |= LightEntityFeature.EFFECT
        return features

    @property
    def _is_dimmer(self) -> bool:
        attrs = self.extra_state_attributes
        return "LIGHT_LEVEL" in attrs or "Brightness Percent" in attrs

    @property
    def color_mode(self) -> ColorMode | None:
        """Return current color mode."""
        attrs = self.extra_state_attributes
        mode = attrs.get("light_color_current_color_mode")
        try:
            mode_i = int(mode)  # type: ignore[arg-type]
            if mode_i == CONTROL4_COLOR_MODE_CCT:
                return ColorMode.COLOR_TEMP
            if mode_i == CONTROL4_COLOR_MODE_XY:
                return ColorMode.XY
        except ValueError, TypeError:
            pass
        if self._attr_color_mode in (self._attr_supported_color_modes or set()):
            return self._attr_color_mode
        return ColorMode.UNKNOWN

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return current XY color."""
        attrs = self.extra_state_attributes
        x = attrs.get("light_color_current_x")
        y = attrs.get("light_color_current_y")
        if x is not None and y is not None:
            return (float(x), float(y))
        return None

    def _to_rate_ms(self, transition: float | None) -> int | None:
        if transition is None:
            return None
        try:
            rate = int(float(transition) * 1000)
        except Exception:  # noqa: BLE001
            return None
        if self._rate_min is not None:
            rate = max(rate, int(self._rate_min))
        if self._rate_max is not None:
            rate = min(rate, int(self._rate_max))
        return max(0, rate)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        c4_light = self.create_api_object()
        transition_length = self._to_rate_ms(kwargs.get(ATTR_TRANSITION))
        effect = kwargs.get(ATTR_EFFECT)
        if effect and effect in self._effects_by_name:
            preset = self._effects_by_name[effect]
            ct = preset.get("color_correlated_temperature")
            if isinstance(ct, (int, float)) and ct > 0 and self._supports_ct:
                ct_i = int(ct)
                if self._ct_min:
                    ct_i = max(ct_i, int(self._ct_min))
                if self._ct_max:
                    ct_i = min(ct_i, int(self._ct_max))
                await c4_light.set_color_temperature(ct_i, rate=transition_length)
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                x = preset.get("color_x")
                y = preset.get("color_y")
                if (
                    self._supports_color
                    and isinstance(x, (int, float))
                    and isinstance(y, (int, float))
                ):
                    await c4_light.set_color_xy(
                        float(x), float(y), rate=transition_length
                    )
                    self._attr_color_mode = ColorMode.XY
            self._current_effect = effect
            self.async_write_ha_state()
            return

        if ATTR_XY_COLOR in kwargs and self._supports_color:
            x, y = kwargs[ATTR_XY_COLOR]
            await c4_light.set_color_xy(float(x), float(y), rate=transition_length)
            self._current_effect = None
            self._attr_color_mode = ColorMode.XY
            self.async_write_ha_state()
            return

        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._supports_ct:
            ct = int(kwargs[ATTR_COLOR_TEMP_KELVIN])
            if self._ct_min is not None:
                ct = max(ct, int(self._ct_min))
            if self._ct_max is not None:
                ct = min(ct, int(self._ct_max))
            await c4_light.set_color_temperature(ct, rate=transition_length)
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._current_effect = None
            self.async_write_ha_state()
            return

        if self._is_dimmer:
            brightness = (
                round(
                    brightness_to_value(
                        CONTROL4_BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS]
                    )
                )
                if ATTR_BRIGHTNESS in kwargs
                else 100
            )
            await c4_light.ramp_to_level(brightness, transition_length or 0)
        else:
            await c4_light.set_level(100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        c4_light = self.create_api_object()
        transition_length = self._to_rate_ms(kwargs.get(ATTR_TRANSITION))
        if self._is_dimmer:
            await c4_light.ramp_to_level(0, transition_length or 0)
        else:
            await c4_light.set_level(0)
