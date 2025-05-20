"""Support for AVM FRITZ!SmartHome lightbulbs."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COLOR_MODE, LOGGER
from .coordinator import FritzboxConfigEntry, FritzboxDataUpdateCoordinator
from .entity import FritzBoxDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome light from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            FritzboxLight(coordinator, ain)
            for ain in devices
            if coordinator.data.devices[ain].has_lightbulb
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


class FritzboxLight(FritzBoxDeviceEntity, LightEntity):
    """The light class for FRITZ!SmartHome lightbulbs."""

    def __init__(
        self,
        coordinator: FritzboxDataUpdateCoordinator,
        ain: str,
    ) -> None:
        """Initialize the FritzboxLight entity."""
        super().__init__(coordinator, ain, None)

        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self.data.has_color:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
        elif self.data.has_level:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        (supported_colors, supported_color_temps) = (
            coordinator.data.supported_color_properties.get(self.data.ain, ({}, []))
        )

        # Fritz!DECT 500 only supports 12 values for hue, with 3 saturations each.
        # Map supported colors to dict {hue: [sat1, sat2, sat3]} for easier lookup
        self._supported_hs: dict[int, list[int]] = {}
        for values in supported_colors.values():
            hue = int(values[0][0])
            self._supported_hs[hue] = [
                int(values[0][1]),
                int(values[1][1]),
                int(values[2][1]),
            ]

        if supported_color_temps:
            # only available for color bulbs
            self._attr_max_color_temp_kelvin = int(max(supported_color_temps))
            self._attr_min_color_temp_kelvin = int(min(supported_color_temps))

    @property
    def is_on(self) -> bool:
        """If the light is currently on or off."""
        return self.data.state  # type: ignore [no-any-return]

    @property
    def brightness(self) -> int:
        """Return the current Brightness."""
        return self.data.level  # type: ignore [no-any-return]

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hs color value."""
        hue = self.data.hue
        saturation = self.data.saturation

        return (hue, float(saturation) * 100.0 / 255.0)

    @property
    def color_temp_kelvin(self) -> int:
        """Return the CT color value."""
        return self.data.color_temp  # type: ignore [no-any-return]

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self.data.has_color:
            if self.data.color_mode == COLOR_MODE:
                return ColorMode.HS
            return ColorMode.COLOR_TEMP
        if self.data.has_level:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            level = kwargs[ATTR_BRIGHTNESS]
            await self.hass.async_add_executor_job(self.data.set_level, level, True)
        if kwargs.get(ATTR_HS_COLOR) is not None:
            # HA gives 0..360 for hue, fritz light only supports 0..359
            unmapped_hue = int(kwargs[ATTR_HS_COLOR][0] % 360)
            unmapped_saturation = round(
                cast(float, kwargs[ATTR_HS_COLOR][1]) * 255.0 / 100.0
            )
            if self.data.fullcolorsupport:
                LOGGER.debug("device has fullcolorsupport, using 'setunmappedcolor'")
                await self.hass.async_add_executor_job(
                    self.data.set_unmapped_color,
                    (unmapped_hue, unmapped_saturation),
                    0,
                    True,
                )
            else:
                LOGGER.debug(
                    "device has no fullcolorsupport, using supported colors with 'setcolor'"
                )
                # find supported hs values closest to what user selected
                hue = min(
                    self._supported_hs.keys(), key=lambda x: abs(x - unmapped_hue)
                )
                saturation = min(
                    self._supported_hs[hue],
                    key=lambda x: abs(x - unmapped_saturation),
                )
                await self.hass.async_add_executor_job(
                    self.data.set_color, (hue, saturation), 0, True
                )

        if kwargs.get(ATTR_COLOR_TEMP_KELVIN) is not None:
            await self.hass.async_add_executor_job(
                self.data.set_color_temp, kwargs[ATTR_COLOR_TEMP_KELVIN], 0, True
            )

        await self.hass.async_add_executor_job(self.data.set_state_on, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.hass.async_add_executor_job(self.data.set_state_off, True)
        await self.coordinator.async_refresh()
