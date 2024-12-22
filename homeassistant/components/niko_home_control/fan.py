"""Setup NikoHomeControlFan."""

from nhc.fan import NHCFan

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NHCController, NikoHomeControlConfigEntry
from .const import PRESET_MODES
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control fan entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlFan(fan, controller, entry.entry_id) for fan in controller.fans
    )


class NikoHomeControlFan(NikoHomeControlEntity, FanEntity):
    """Representation of an Niko fan."""

    _attr_name = None
    _action = NHCFan

    def __init__(
        self, action: NHCFan, controller: NHCController, unique_id: str
    ) -> None:
        """Set up the Niko Home Control fan platform."""
        super().__init__(action, controller, unique_id)
        self._attr_preset_modes = PRESET_MODES
        self._attr_supported_features = FanEntityFeature.PRESET_MODE
        self._attr_enable_turn_on_off_backwards_compatibility = False

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        self._action.set_mode(preset_mode)

    def update_state(self) -> None:
        """Handle updates from the controller."""
        self._attr_preset_mode = PRESET_MODES[self._action.state]
