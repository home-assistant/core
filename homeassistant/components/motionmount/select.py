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
    _attr_current_option: str | None = None

    def __init__(
        self,
        mm: motionmount.MotionMount,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize Preset selector."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-preset"

    def _update_options(self, presets: dict[int, str]) -> None:
        """Convert presets to select options."""
        options = [WALL_PRESET_NAME]
        for index, name in presets.items():
            options.append(f"{index}: {name}")

        self._attr_options = options

    async def async_update(self) -> None:
        """Get latest state from MotionMount."""
        presets = await self.mm.get_presets()
        self._update_options(presets)

        if self._attr_current_option is None:
            self._attr_current_option = self._attr_options[0]

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        await self.mm.go_to_preset(index)
        self._attr_current_option = option

        # Perform an update so we detect changes to the presets (changes are not pushed)
        self.async_schedule_update_ha_state(True)
