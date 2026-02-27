"""Select entities for Trinnov Altitude integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from trinnov_altitude.command_bridge import parse_upmixer_mode
from trinnov_altitude.const import UpmixerMode

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select entities from config entry."""
    device = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TrinnovAltitudeSourceSelect(device),
            TrinnovAltitudePresetSelect(device),
            TrinnovAltitudeUpmixerSelect(device),
        ]
    )


class TrinnovAltitudeSourceSelect(TrinnovAltitudeEntity, SelectEntity):
    """Representation of a Trinnov Altitude source select entity."""

    _attr_translation_key = "source"
    _attr_name = "Source"

    def __init__(self, device) -> None:
        """Initialize source select entity."""
        super().__init__(device)
        self._attr_unique_id = f"{self._attr_unique_id}-source-select"

    @property
    def current_option(self) -> str | None:
        """Return current source."""
        return self._device.state.source

    @property
    def options(self) -> list[str]:
        """Return available source options."""
        return list(self._device.state.sources.values())

    async def async_select_option(self, option: str) -> None:
        """Change selected source."""
        try:
            await self._device.source_set_by_name(option)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc


class TrinnovAltitudePresetSelect(TrinnovAltitudeEntity, SelectEntity):
    """Representation of a Trinnov Altitude preset select entity."""

    _attr_translation_key = "preset"
    _attr_name = "Preset"

    def __init__(self, device) -> None:
        """Initialize preset select entity."""
        super().__init__(device)
        self._attr_unique_id = f"{self._attr_unique_id}-preset-select"

    @property
    def current_option(self) -> str | None:
        """Return current preset."""
        return self._device.state.preset

    @property
    def options(self) -> list[str]:
        """Return available preset options."""
        return list(self._device.state.presets.values())

    async def async_select_option(self, option: str) -> None:
        """Change selected preset."""
        for preset_id, name in self._device.state.presets.items():
            if name == option:
                await self._device.preset_set(preset_id)
                return


class TrinnovAltitudeUpmixerSelect(TrinnovAltitudeEntity, SelectEntity):
    """Representation of a Trinnov Altitude upmixer select entity."""

    _attr_translation_key = "upmixer"
    _attr_name = "Upmixer"

    def __init__(self, device) -> None:
        """Initialize upmixer select entity."""
        super().__init__(device)
        self._attr_unique_id = f"{self._attr_unique_id}-upmixer-select"

    @property
    def current_option(self) -> str | None:
        """Return current upmixer."""
        upmixer = self._device.state.upmixer
        if upmixer is None:
            return None
        try:
            return parse_upmixer_mode(upmixer).value
        except ValueError:
            return None

    @property
    def options(self) -> list[str]:
        """Return available upmixer options."""
        return [mode.value for mode in UpmixerMode]

    async def async_select_option(self, option: str) -> None:
        """Change selected upmixer."""
        try:
            mode = parse_upmixer_mode(option)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self._device.upmixer_set(mode)
