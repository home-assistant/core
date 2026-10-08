"""Light platform for TIS Control dimmer channels."""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import TISConfigEntry
from .entity import TISEntity
from .hub import TISHub

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0

LEVEL_SCALE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TISConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TIS Control lights."""
    hub = entry.runtime_data
    async_add_entities(TISLight(hub, spec) for spec in hub.devices)


class TISLight(TISEntity, LightEntity):
    """A dimmer channel."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_translation_key = "channel"

    def __init__(self, hub: TISHub, spec: dict[str, Any]) -> None:
        """Initialize the light."""
        super().__init__(hub, spec)
        self._attr_translation_placeholders = {"channel": str(self.channel)}
        self._last_on_level = 100

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the channel is on."""
        return bool(self.level)

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness, 0-255."""
        return value_to_brightness(LEVEL_SCALE, level) if (level := self.level) else 0

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the channel on, optionally to a brightness and with a fade."""
        if ATTR_BRIGHTNESS in kwargs:
            level = max(
                1, round(brightness_to_value(LEVEL_SCALE, kwargs[ATTR_BRIGHTNESS]))
            )
        elif (current := self.level) and current > 0:
            level = current
        else:
            level = self._last_on_level
        self._set(level, kwargs.get(ATTR_TRANSITION))

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the channel off."""
        if (current := self.level) and current > 0:
            self._last_on_level = current
        self._set(0, kwargs.get(ATTR_TRANSITION))

    def _set(self, level: int, transition: float | None) -> None:
        self.hub.gateway.set_channel(
            *self.address, self.channel, level, round(transition or 0)
        )
        # The module confirms on the bus within ~0.1 s; show the new state right away.
        self.hub.channels[(*self.address, self.channel)] = level
        self.async_write_ha_state()
