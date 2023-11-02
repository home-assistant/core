"""Support for MotionMount numeric control."""
import motionmount  # type: ignore[import]

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    presets = await coordinator.mm.get_presets()

    async_add_entities(
        [
            MotionMountPresets(coordinator.mm, entry.entry_id, presets),
        ]
    )


class MotionMountPresets(SelectEntity):
    """The presets of a MotionMount."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Preset"

    def __init__(
        self,
        mm: motionmount.MotionMount,
        unique_id: str,
        presets: dict[int, str],
    ) -> None:
        """Initialize Extension number."""
        self._attr_unique_id = f"{unique_id}-preset"
        self._mm = mm

        self._update_options(presets)
        self._attr_current_option = self._attr_options[0]

    def _update_options(self, presets: dict[int, str]) -> None:
        """Convert preset to select options."""
        options = ["0: Wall"]
        for index, name in presets.items():
            options.append(f"{index}: {name}")

        self._attr_options = options

    async def async_update(self) -> None:
        """Get latest state from MotionMount."""
        presets = await self._mm.get_presets()
        self._update_options(presets)

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        await self._mm.go_to_preset(index)
        self._attr_current_option = option
        self.async_schedule_update_ha_state(True)
