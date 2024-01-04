"""Support for MotionMount numeric control."""
import motionmount

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    mm = hass.data[DOMAIN][entry.entry_id]

    presets = await mm.get_presets()

    async_add_entities((MotionMountPresets(mm, entry, presets),))


class MotionMountPresets(MotionMountEntity, SelectEntity):
    """The presets of a MotionMount."""

    _attr_translation_key = "motionmount_preset"

    def __init__(
        self,
        mm: motionmount.MotionMount,
        config_entry: ConfigEntry,
        presets: dict[int, str],
    ) -> None:
        """Initialize Preset selector."""
        super().__init__(mm, config_entry)
        self._attr_unique_id = f"{self._base_unique_id}-preset"

        self._update_options(presets)
        self._attr_current_option = self._attr_options[0]

    def _update_options(self, presets: dict[int, str]) -> None:
        """Convert presets to select options."""
        options = ["0_wall"]
        for index, name in presets.items():
            options.append(f"{index}: {name}")

        self._attr_options = options

    async def async_update(self) -> None:
        """Get latest state from MotionMount."""
        presets = await self.mm.get_presets()
        self._update_options(presets)

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        await self.mm.go_to_preset(index)
        self._attr_current_option = option

        # Perform an update so we detect changes to the presets (changes are not pushed)
        self.async_schedule_update_ha_state(True)
