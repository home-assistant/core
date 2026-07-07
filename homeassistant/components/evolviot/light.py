"""Light platform for EvolvIOT."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator, evolviot_entity_domain
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "light"
COLOR_DOMAIN = "color"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EvolvIOT lights."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: EvolvIOTDataUpdateCoordinator = data[DATA_COORDINATOR]
    known = data[DATA_KNOWN_ENTITIES].setdefault(PLATFORM_DOMAIN, set())

    def add_new_entities() -> None:
        entities = []
        for entity in (
            *coordinator.entities_for_domain(PLATFORM_DOMAIN),
            *coordinator.entities_for_domain(COLOR_DOMAIN),
        ):
            entity_id = entity["entity_id"]
            if entity_id in known:
                continue
            known.add(entity_id)
            if evolviot_entity_domain(entity) == COLOR_DOMAIN:
                entities.append(EvolvIOTColorLight(coordinator, entity))
            else:
                entities.append(EvolvIOTLight(coordinator, entity))
        if entities:
            async_add_entities(entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class EvolvIOTLight(EvolvIOTEntity, LightEntity):
    """EvolvIOT light entity."""

    @property
    def _supports_brightness(self) -> bool:
        capabilities = self.backend_entity.get("capabilities") or {}
        control = self.backend_entity.get("control") or {}
        metadata = " ".join(
            str(value or "")
            for value in (
                control.get("key"),
                control.get("name"),
                self.backend_entity.get("unique_id"),
                self.backend_entity.get("entity_id"),
                self.backend_entity.get("name"),
            )
        ).lower()
        return bool(capabilities.get("supports_brightness")) or "brightness" in metadata

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        if self._supports_brightness:
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        if self._supports_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        state = self.backend_state.get("state")
        if state is None:
            return None
        return str(state).lower() == "on"

    @property
    def brightness(self) -> int | None:
        """Return brightness on Home Assistant's 0-255 scale."""
        value = self.backend_state.get("attributes", {}).get("brightness")
        if value is None:
            return None
        return round(max(0, min(100, int(value))) * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(int(kwargs[ATTR_BRIGHTNESS]) * 100 / 255)
            await self._async_send_command({"brightness": brightness})
            return
        await self._async_send_command({"command": "turn_on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_send_command({"command": "turn_off"})


class EvolvIOTColorLight(EvolvIOTEntity, LightEntity):
    """EvolvIOT color control exposed as a color-capable light."""

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        return {ColorMode.RGB}

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        return ColorMode.RGB

    @property
    def is_on(self) -> bool | None:
        """Return true while the color control is available."""
        if not self.backend_state:
            return None
        return self.available

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return current RGB color."""
        value = self.backend_state.get("raw_value", self.backend_state.get("state"))
        return _parse_rgb_color(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the color."""
        if ATTR_RGB_COLOR not in kwargs:
            return

        red, green, blue = kwargs[ATTR_RGB_COLOR]
        await self._async_send_command({"value": f"{red},{green},{blue}"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Color-only controls do not expose power state."""


def _parse_rgb_color(value: Any) -> tuple[int, int, int] | None:
    """Parse an EvolvIOT RGB value."""
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("#") and len(value) == 7:
            try:
                return (
                    int(value[1:3], 16),
                    int(value[3:5], 16),
                    int(value[5:7], 16),
                )
            except ValueError:
                return None

        parts = value.split(",")
        if len(parts) == 3:
            try:
                red, green, blue = parts
                return (
                    max(0, min(255, int(red))),
                    max(0, min(255, int(green))),
                    max(0, min(255, int(blue))),
                )
            except ValueError:
                return None

    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            red, green, blue = value
            return (
                max(0, min(255, int(red))),
                max(0, min(255, int(green))),
                max(0, min(255, int(blue))),
            )
        except TypeError, ValueError:
            return None

    return None
