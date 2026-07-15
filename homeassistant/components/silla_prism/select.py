"""Select platform for the Silla Prism integration."""

from typing import override

from pysillaprism import SETTABLE_MODES

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PORT
from .coordinator import PrismConfigEntry, PrismCoordinator
from .entity import PrismEntity

PARALLEL_UPDATES = 0

_OPTION_TO_MODE = {mode.name.lower(): mode for mode in SETTABLE_MODES}
_MODE_TO_OPTION = {mode: name for name, mode in _OPTION_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrismConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Prism select entities."""
    async_add_entities([PrismModeSelect(entry.runtime_data)])


class PrismModeSelect(PrismEntity, SelectEntity):
    """Charging mode selector (Solar/Normal/Pause)."""

    _attr_translation_key = "charging_mode"
    _attr_options = list(_OPTION_TO_MODE)

    def __init__(self, coordinator: PrismCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, "charging_mode")

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current mode, or None when not user-settable.

        Prism can report ``AUTOLIMIT_PAUSE`` (load balancing suspended the
        session), which is not one of the selectable options; it surfaces on
        the status sensor instead.
        """
        mode = self.coordinator.device.status.port(PORT).mode
        return _MODE_TO_OPTION.get(mode) if mode is not None else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the charging mode."""
        await self.coordinator.device.set_mode(_OPTION_TO_MODE[option], PORT)
