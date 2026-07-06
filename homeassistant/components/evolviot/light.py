"""Light platform for EvolvIOT."""

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_KNOWN_ENTITIES, DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator
from .entity import EvolvIOTEntity

PLATFORM_DOMAIN = "light"


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
        for entity in coordinator.entities_for_domain(PLATFORM_DOMAIN):
            entity_id = entity["entity_id"]
            if entity_id in known:
                continue
            known.add(entity_id)
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
        return bool(capabilities.get("supports_brightness"))

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
