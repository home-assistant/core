"""Switch platform for madVR Envy."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MadvrEnvyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MadvrEnvyToneMapSwitch(entry.runtime_data.coordinator)])


class MadvrEnvyToneMapSwitch(MadvrEnvyEntity, SwitchEntity):
    """Switch for Tone Mapping."""

    _attr_translation_key = "tone_map"
    _attr_icon = "mdi:lightbulb-on"

    def __init__(self, coordinator) -> None:  # noqa: ANN001
        super().__init__(coordinator, "tone_map")

    @property
    def is_on(self) -> bool | None:
        value = self.data.get("tone_map_enabled")
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:  # noqa: ANN003
        await self._execute("ToneMapOn", self._client.tone_map_on)

    async def async_turn_off(self, **kwargs) -> None:  # noqa: ANN003
        await self._execute("ToneMapOff", self._client.tone_map_off)
