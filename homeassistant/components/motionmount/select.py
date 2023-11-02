"""Support for MotionMount numeric control."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    presets = await coordinator.mm.get_presets()

    async_add_entities(
        [
            MotionMountPresets(coordinator, entry.entry_id, presets),
        ]
    )


class MotionMountPresets(MotionMountEntity, SelectEntity):
    """The presets of a MotionMount."""

    _attr_name = "Preset"

    def __init__(self, coordinator, unique_id, presets):
        """Initialize Extension number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-preset"

        options = ["0: Wall"]
        for index, name in presets.items():
            options.append(f"{index}: {name}")

        self._attr_options = options
        self._attr_current_option = options[0]

    @callback
    def _handle_coordinator_update(self) -> None:
        #        self._attr_current_option
        #        self.async_write_ha_state()
        return

    async def async_select_option(self, option: str) -> None:
        """Set the new option."""
        index = int(option[:1])
        await self.coordinator.mm.go_to_preset(index)
        self._attr_current_option = option
        self.async_write_ha_state()
