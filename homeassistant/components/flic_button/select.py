"""Select platform for Flic Button integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .const import CONF_PUSH_TWIST_MODE, PushTwistMode
from .coordinator import FlicCoordinator, format_selector_dispatcher_name
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0

# 12 slot options (1-indexed for user display)
SLOT_OPTIONS = [f"Slot {i}" for i in range(1, 13)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button select entities."""
    coordinator = entry.runtime_data

    # Only add select entity for Twist devices in selector mode
    push_twist_mode = entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
    if coordinator.is_twist and push_twist_mode == PushTwistMode.SELECTOR:
        async_add_entities([FlicSelectedSlotSelect(coordinator)])


class FlicSelectedSlotSelect(FlicButtonEntity, SelectEntity):
    """Select entity for Flic Twist selected slot."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "selected_slot"
    _attr_options = SLOT_OPTIONS

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the selected slot select entity.

        Args:
            coordinator: Flic coordinator instance

        """
        super().__init__(coordinator)
        self._current_slot_index: int = 0  # Default to Slot 1 (index 0)
        self._attr_unique_id = f"{coordinator.client.address}-selected-slot"

    @property
    def current_option(self) -> str:
        """Return current selected slot option."""
        return SLOT_OPTIONS[self._current_slot_index]

    async def async_added_to_hass(self) -> None:
        """Subscribe to selector updates when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_selector_dispatcher_name(self.coordinator.client.address),
                self._handle_selector_update,
            )
        )

    @callback
    def _handle_selector_update(self, selector_index: int) -> None:
        """Handle selector slot update from push_twist rotation.

        Args:
            selector_index: The selected slot index (0-11)

        """
        if 0 <= selector_index <= 11:
            self._current_slot_index = selector_index
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle user selection (read-only, no-op).

        This entity is read-only - it reflects the physical dial position
        set during push+twist rotation. User cannot change it from HA.
        """
