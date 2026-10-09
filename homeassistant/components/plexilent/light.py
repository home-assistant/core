"""Light platform for the Plexilent integration."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import PlexilentConfigEntry, PlexilentCoordinator
from .entity import PlexilentEntity, add_entities

PARALLEL_UPDATES = 0

# Device type -> colour modes. 5ch = colour + white, ct = white, dim, onoff.
MODES = {
    "5ch": {ColorMode.HS, ColorMode.COLOR_TEMP},
    "ct": {ColorMode.COLOR_TEMP},
    "dim": {ColorMode.BRIGHTNESS},
    "onoff": {ColorMode.ONOFF},
}
PERCENT = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlexilentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lights of the account."""
    add_entities(entry, async_add_entities, set(MODES), PlexilentLight)


class PlexilentLight(PlexilentEntity, LightEntity):
    """A Plexilent light: colour + white, white, dimmable or on/off."""

    def __init__(self, coordinator: PlexilentCoordinator, device_id: str) -> None:
        """Initialize the light with the colour modes of its type."""
        super().__init__(coordinator, device_id)
        device = self.device
        self._attr_supported_color_modes = MODES[device.type]
        if ColorMode.COLOR_TEMP in MODES[device.type]:
            self._attr_min_color_temp_kelvin = device.cct_min
            self._attr_max_color_temp_kelvin = device.cct_max

    @property
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return bool(self.device.on)

    @property
    def color_mode(self) -> ColorMode:
        """Return the colour mode: colour while a colour is set, else white."""
        modes = MODES[self.device.type]
        if len(modes) == 1:
            return next(iter(modes))
        return ColorMode.HS if self.device.hs else ColorMode.COLOR_TEMP

    @property
    def brightness(self) -> int | None:
        """Return the brightness, 0-255."""
        level = self.device.brightness
        return None if level is None else value_to_brightness(PERCENT, level)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the white temperature in Kelvin."""
        return self.device.cct

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the colour as hue and saturation."""
        return self.device.hs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, with brightness, white or colour if given."""
        fields: dict[str, Any] = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            # Never 0 %: the cloud treats 0 % as off.
            fields["brightness"] = max(
                1, round(brightness_to_value(PERCENT, kwargs[ATTR_BRIGHTNESS]))
            )
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            fields["cct"] = kwargs[ATTR_COLOR_TEMP_KELVIN]
        if ATTR_HS_COLOR in kwargs:
            fields["hs"] = kwargs[ATTR_HS_COLOR]
        await self._send(**fields)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._send(on=False)
