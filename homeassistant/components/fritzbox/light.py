"""Support for AVM FRITZ!SmartHome lightbulbs."""

from __future__ import annotations

from typing import Any, cast

from requests.exceptions import HTTPError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzboxDataUpdateCoordinator, FritzBoxDeviceEntity
from .const import COLOR_MODE, COLOR_TEMP_MODE, LOGGER
from .coordinator import FritzboxConfigEntry

SUPPORTED_COLOR_MODES = {ColorMode.COLOR_TEMP, ColorMode.HS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        self._supported_hs: dict[int, list[int]] = {}

    @property
    def is_on(self) -> bool:
        """If the light is currently on or off."""
        return self.data.state  # type: ignore [no-any-return]

    @property
    def brightness(self) -> int:
        """Return the current Brightness."""
        return self.data.level  # type: ignore [no-any-return]

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        if self.data.color_mode != COLOR_MODE:
            return None

        hue = self.data.hue
        saturation = self.data.saturation

        return (hue, float(saturation) * 100.0 / 255.0)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value."""
        if self.data.color_mode != COLOR_TEMP_MODE:
            return None

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

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        if self.data.has_color:
            return SUPPORTED_COLOR_MODES
        if self.data.has_level:
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            level = kwargs[ATTR_BRIGHTNESS]
            await self.hass.async_add_executor_job(self.data.set_level, level)
        if kwargs.get(ATTR_HS_COLOR) is not None:
            # Try setunmappedcolor first. This allows free color selection,
            # but we don't know if its supported by all devices.
            try:
                # HA gives 0..360 for hue, fritz light only supports 0..359
                unmapped_hue = int(kwargs[ATTR_HS_COLOR][0] % 360)
                unmapped_saturation = round(
                    cast(float, kwargs[ATTR_HS_COLOR][1]) * 255.0 / 100.0
                )
                await self.hass.async_add_executor_job(
                    self.data.set_unmapped_color, (unmapped_hue, unmapped_saturation)
                )
            # This will raise 400 BAD REQUEST if the setunmappedcolor is not available
            except HTTPError as err:
                if err.response.status_code != 400:
                    raise
                LOGGER.debug(
                    "fritzbox does not support method 'setunmappedcolor', fallback to"
                    " 'setcolor'"
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
                    self.data.set_color, (hue, saturation)
                )

        if kwargs.get(ATTR_COLOR_TEMP_KELVIN) is not None:
            await self.hass.async_add_executor_job(
                self.data.set_color_temp, kwargs[ATTR_COLOR_TEMP_KELVIN]
            )

        await self.hass.async_add_executor_job(self.data.set_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.hass.async_add_executor_job(self.data.set_state_off)
        await self.coordinator.async_refresh()

    async def async_added_to_hass(self) -> None:
        """Get light attributes from device after entity is added to hass."""
        await super().async_added_to_hass()
        supported_colors = await self.hass.async_add_executor_job(
            self.coordinator.data.devices[self.ain].get_colors
        )
        supported_color_temps = await self.hass.async_add_executor_job(
            self.coordinator.data.devices[self.ain].get_color_temps
        )

        if supported_color_temps:
            # only available for color bulbs
            self._attr_max_color_temp_kelvin = int(max(supported_color_temps))
            self._attr_min_color_temp_kelvin = int(min(supported_color_temps))

        # Fritz!DECT 500 only supports 12 values for hue, with 3 saturations each.
        # Map supported colors to dict {hue: [sat1, sat2, sat3]} for easier lookup
        for values in supported_colors.values():
            hue = int(values[0][0])
            self._supported_hs[hue] = [
                int(values[0][1]),
                int(values[1][1]),
                int(values[2][1]),
            ]
