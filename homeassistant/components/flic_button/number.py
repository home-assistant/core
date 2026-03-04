"""Number platform for Flic Button integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlicButtonConfigEntry
from .const import CONF_PUSH_TWIST_MODE, DOMAIN, PushTwistMode
from .coordinator import (
    FlicCoordinator,
    format_duo_dial_dispatcher_name,
    format_push_twist_position_dispatcher_name,
    format_slot_dispatcher_name,
    format_twist_position_dispatcher_name,
)
from .entity import FlicButtonEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlicButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flic Button number entities."""
    coordinator = entry.runtime_data

    entities: list[NumberEntity] = []

    # Add number entities for Twist devices based on push-twist mode
    if coordinator.is_twist:
        push_twist_mode = entry.options.get(CONF_PUSH_TWIST_MODE, PushTwistMode.DEFAULT)
        if push_twist_mode == PushTwistMode.SELECTOR:
            # SELECTOR mode: 12 per-slot entities
            entities.extend(TwistSlotNumber(coordinator, i) for i in range(12))
        else:
            # DEFAULT/CONTINUOUS mode: 2 slider entities (free rotation + push-twist)
            entities.append(PushTwistPositionNumber(coordinator))
            entities.append(TwistPositionNumber(coordinator))

    # Add dial number entities for Duo devices (one per button)
    if coordinator.is_duo:
        entities.append(DuoDialNumber(coordinator, button_index=0))  # Big button
        entities.append(DuoDialNumber(coordinator, button_index=1))  # Small button

    if entities:
        async_add_entities(entities)


class TwistSlotNumber(FlicButtonEntity, NumberEntity):
    """Number entity showing a Twist slot position (0-100%)."""

    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: FlicCoordinator, mode_index: int) -> None:
        """Initialize the slot number entity."""
        super().__init__(coordinator)
        self._mode_index = mode_index
        self._attr_native_value: float = coordinator.get_slot_value(mode_index)

        # Translation key for entity name (slot_1 through slot_12)
        self._attr_translation_key = f"slot_{mode_index + 1}"

        # Unique ID
        self._attr_unique_id = f"{coordinator.client.address}-slot-{mode_index}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to slot position updates when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_slot_dispatcher_name(
                    self.coordinator.client.address, self._mode_index
                ),
                self._handle_slot_update,
            )
        )

    @callback
    def _handle_slot_update(self, percentage: float) -> None:
        """Handle slot position update from rotation."""
        self._attr_native_value = percentage
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the twist slot position and send to device."""
        await self.coordinator.async_update_twist_position(self._mode_index, value)
        self._attr_native_value = value
        self.coordinator.set_slot_value(self._mode_index, value)
        self.async_write_ha_state()


class TwistPositionNumber(FlicButtonEntity, NumberEntity):
    """Number entity showing Twist free-rotation position (0-100%).

    Active in DEFAULT push-twist mode. Tracks rotation without
    pressing the button (mode 0). Uses integer percentages.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_translation_key = "twist_position"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the twist position number entity."""
        super().__init__(coordinator)
        self._attr_native_value: int = int(coordinator.get_slot_value(0))
        self._attr_unique_id = f"{coordinator.client.address}-twist-position"

    async def async_added_to_hass(self) -> None:
        """Subscribe to twist position updates when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_twist_position_dispatcher_name(self.coordinator.client.address),
                self._handle_position_update,
            )
        )

    @callback
    def _handle_position_update(self, percentage: float) -> None:
        """Handle twist position update from rotation."""
        self._attr_native_value = int(percentage)
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the twist position and send to device."""
        int_value = int(value)
        await self.coordinator.async_update_twist_position(0, int_value)
        self._attr_native_value = int_value
        self.coordinator.set_slot_value(0, int_value)
        self.async_write_ha_state()


class PushTwistPositionNumber(FlicButtonEntity, NumberEntity):
    """Number entity showing push-twist rotation position (0-100%)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_translation_key = "push_twist_position"

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the push-twist position number entity."""
        super().__init__(coordinator)
        self._attr_native_value: int = int(coordinator.get_slot_value(12))
        self._attr_unique_id = f"{coordinator.client.address}-push-twist-position"

    async def async_added_to_hass(self) -> None:
        """Subscribe to push-twist position updates when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_push_twist_position_dispatcher_name(
                    self.coordinator.client.address
                ),
                self._handle_position_update,
            )
        )

    @callback
    def _handle_position_update(self, percentage: float) -> None:
        """Handle push-twist position update from rotation."""
        self._attr_native_value = int(percentage)
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the push-twist position and send to device."""
        int_value = int(value)
        await self.coordinator.async_update_twist_position(12, int_value)
        self._attr_native_value = int_value
        self.coordinator.set_slot_value(12, int_value)
        self.async_write_ha_state()


class DuoDialNumber(FlicButtonEntity, NumberEntity):
    """Number entity showing the Flic Duo dial position (0-100%).

    Each button has its own dial position. The dial position is based on
    rotation where 120 degrees = 100%. Rotating clockwise increases the value,
    counter-clockwise decreases it. The value is clamped to 0-100%.
    """

    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: FlicCoordinator, button_index: int) -> None:
        """Initialize the Duo dial number entity."""
        super().__init__(coordinator)
        self._button_index = button_index
        self._attr_native_value: float = 0.0

        # Translation key based on button (big_dial for index 0, small_dial for index 1)
        self._attr_translation_key = "big_dial" if button_index == 0 else "small_dial"

        # Unique ID includes button index
        self._attr_unique_id = f"{coordinator.client.address}-duo-dial-{button_index}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to dial position updates when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_duo_dial_dispatcher_name(
                    self.coordinator.client.address, self._button_index
                ),
                self._handle_dial_update,
            )
        )

    @callback
    def _handle_dial_update(self, percentage: float) -> None:
        """Handle dial position update from rotation."""
        self._attr_native_value = percentage
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Handle user setting value (read-only)."""
        raise ServiceValidationError(
            "This entity is read-only and reflects the physical dial position",
            translation_domain=DOMAIN,
            translation_key="read_only_entity",
        )
