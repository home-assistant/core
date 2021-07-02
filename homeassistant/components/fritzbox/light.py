"""Support for AVM FRITZ!SmartHome lightbulbs."""
from __future__ import annotations

from typing import Any

from pyfritzhome.fritzhomedevice import FritzhomeDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import color

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN
from .model import EntityInfo, LightExtraAttributes

SUPPORTED_COLOR_MODES = {COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome light from ConfigEntry."""
    entities: list[FritzboxLight] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if not device.has_lightbulb:
            continue

        supported_color_temps = await hass.async_add_executor_job(
            device.get_color_temps
        )

        supported_colors = await hass.async_add_executor_job(device.get_colors)

        entities.append(
            FritzboxLight(
                {
                    ATTR_NAME: f"{device.name}",
                    ATTR_ENTITY_ID: f"{device.ain}",
                    ATTR_UNIT_OF_MEASUREMENT: None,
                    ATTR_DEVICE_CLASS: None,
                },
                coordinator,
                ain,
                supported_colors,
                supported_color_temps,
            )
        )

    async_add_entities(entities)


class FritzboxLight(FritzBoxEntity, LightEntity):
    """The light class for FRITZ!SmartHome lightbulbs."""

    def __init__(
        self,
        entity_info: EntityInfo,
        coordinator: DataUpdateCoordinator[dict[str, FritzhomeDevice]],
        ain: str,
        supported_colors: dict,
        supported_color_temps: list[str],
    ) -> None:
        """Initialize the FritzboxLight entity."""
        super().__init__(entity_info, coordinator, ain)

        max_kelvin = int(max(supported_color_temps))
        min_kelvin = int(min(supported_color_temps))

        # max kelvin is min mireds and min kelvin is max mireds
        self._attr_min_mireds = color.color_temperature_kelvin_to_mired(max_kelvin)
        self._attr_max_mireds = color.color_temperature_kelvin_to_mired(min_kelvin)

        # Fritz!DECT 500 only supports 12 values for hue, with 3 saturations each.
        # Map supported colors to dict {hue: [sat1, sat2, sat3]} for easier lookup
        self._supported_hs = {}
        for values in supported_colors.values():
            hue = int(values[0][0])
            self._supported_hs[hue] = [
                int(values[0][1]),
                int(values[1][1]),
                int(values[2][1]),
            ]

    @property
    def available(self) -> bool:
        """Return if lightbulb is available."""
        return self.device.present  # type: ignore [no-any-return]

    @property
    def is_on(self) -> bool:
        """If the light is currently on or off."""
        return self.device.state  # type: ignore [no-any-return]

    @property
    def brightness(self) -> int:
        """Return the current Brightness."""
        return self.device.level  # type: ignore [no-any-return]

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        # Don't return hue and saturation unless in color mode
        if self.device.color_mode != "1":
            return None

        hue = self.device.hue
        saturation = self.device.saturation

        return (hue, float(saturation) * 100.0 / 255.0)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value."""
        # Don't return color temperature unless in color temperature mode
        if self.device.color_mode != "4":
            return None

        kelvin = self.device.color_temp
        return color.color_temperature_kelvin_to_mired(kelvin)

    @property
    def supported_color_modes(self) -> set:
        """Flag supported color modes."""
        return SUPPORTED_COLOR_MODES

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            level = kwargs[ATTR_BRIGHTNESS]
            await self.hass.async_add_executor_job(self.device.set_level, level)
        if kwargs.get(ATTR_HS_COLOR) is not None:
            hass_hue = int(kwargs[ATTR_HS_COLOR][0])
            hass_saturation = round(kwargs[ATTR_HS_COLOR][1] * 255.0 / 100.0)
            # find supported hs values closest to what user selected
            hue = min(self._supported_hs.keys(), key=lambda x: abs(x - hass_hue))
            saturation = min(
                self._supported_hs[hue], key=lambda x: abs(x - hass_saturation)
            )
            await self.hass.async_add_executor_job(
                self.device.set_color, (hue, saturation)
            )

        if kwargs.get(ATTR_COLOR_TEMP) is not None:
            kelvin = color.color_temperature_kelvin_to_mired(kwargs[ATTR_COLOR_TEMP])
            await self.hass.async_add_executor_job(self.device.set_color_temp, kelvin)

        await self.hass.async_add_executor_job(self.device.set_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.hass.async_add_executor_job(self.device.set_state_off)
        await self.coordinator.async_refresh()

    @property
    def extra_state_attributes(self) -> LightExtraAttributes:
        """Return the state attributes of the device."""
        attrs: LightExtraAttributes = {
            ATTR_BRIGHTNESS: self.device.level,
            ATTR_COLOR_TEMP: self.color_temp,
            ATTR_HS_COLOR: self.hs_color,
        }

        return attrs
