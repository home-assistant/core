"""Support for MotionMount numeric control."""

import motionmount

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, WALL_PRESET_NAME
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MotionMountPresets(mm, entry)], True)


class MotionMountPresets(MotionMountEntity, SelectEntity):
    """The presets of a MotionMount."""

    _attr_translation_key = "motionmount_preset"

    def __init__(
        self,
        mm: motionmount.MotionMount,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize Preset selector."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-preset"
        self._presets: list[motionmount.Preset] = []

    def _update_options(self, presets: list[motionmount.Preset]) -> None:
        """Convert presets to select options."""
        options = [f"{preset.index}: {preset.name}" for preset in presets]
        options.insert(0, WALL_PRESET_NAME)

        self._attr_options = options

    async def async_update(self) -> None:
        """Get latest state from MotionMount."""
        self._presets = await self.mm.get_presets()
        self._update_options(self._presets)

    @property
    def current_option(self) -> str | None:
        """Get the current option."""
        # When the mount is moving we return the currently selected option
        if self.mm.is_moving:
            return self._attr_current_option

        # When the mount isn't moving we select the option that matches the current position
        self._attr_current_option = None
        if self.mm.extension == 0 and self.mm.turn == 0:
            self._attr_current_option = self._attr_options[0]  # Select Wall preset
        else:
            for preset in self._presets:
                if (
                    preset.extension == self.mm.extension
                    and preset.turn == self.mm.turn
                ):
                    self._attr_current_option = f"{preset.index}: {preset.name}"
                    break

        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        await self.mm.go_to_preset(index)
        self._attr_current_option = option

        # Perform an update so we detect changes to the presets (changes are not pushed)
        self.async_schedule_update_ha_state(True)
