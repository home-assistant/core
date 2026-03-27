"""Cover platform for Liebherr integration."""

from __future__ import annotations

from typing import Any

from pyliebherrhomeapi import AutoDoorControl, DoorState, ZonePosition

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import ZONE_POSITION_MAP, LiebherrEntity

PARALLEL_UPDATES = 1


def _create_cover_entities(
    coordinators: list[LiebherrCoordinator],
) -> list[LiebherrAutoDoor]:
    """Create cover entities for the given coordinators."""
    entities: list[LiebherrAutoDoor] = []

    for coordinator in coordinators:
        has_multiple_zones = len(coordinator.data.get_temperature_controls()) > 1

        entities.extend(
            LiebherrAutoDoor(
                coordinator=coordinator,
                zone_id=control.zone_id,
                has_multiple_zones=has_multiple_zones,
            )
            for control in coordinator.data.controls
            if isinstance(control, AutoDoorControl)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr cover entities."""
    async_add_entities(
        _create_cover_entities(list(entry.runtime_data.coordinators.values()))
    )

    @callback
    def _async_new_device(coordinators: list[LiebherrCoordinator]) -> None:
        """Add cover entities for new devices."""
        async_add_entities(_create_cover_entities(coordinators))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_device_{entry.entry_id}", _async_new_device
        )
    )


class LiebherrAutoDoor(LiebherrEntity, CoverEntity):
    """Representation of a Liebherr auto door."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_translation_key = "auto_door"
    _optimistic_state: bool | None = None

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        zone_id: int,
        has_multiple_zones: bool,
    ) -> None:
        """Initialize the auto door entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.device_id}_auto_door_{zone_id}"

        # Add zone suffix only for multi-zone devices
        if has_multiple_zones:
            temp_controls = coordinator.data.get_temperature_controls()
            if (
                (tc := temp_controls.get(zone_id))
                and isinstance(tc.zone_position, ZonePosition)
                and (zone_key := ZONE_POSITION_MAP.get(tc.zone_position))
            ):
                self._attr_translation_key = f"auto_door_{zone_key}"

    @property
    def _auto_door_control(self) -> AutoDoorControl | None:
        """Get the auto door control for this zone."""
        return self.coordinator.data.get_auto_door_controls().get(self._zone_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._auto_door_control is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()

    @property
    def is_closed(self) -> bool | None:
        """Return if the door is closed."""
        if self._optimistic_state is not None:
            return False
        control = self._auto_door_control
        if control is None or control.value is None:
            return None
        return control.value == DoorState.CLOSED

    @property
    def is_opening(self) -> bool | None:
        """Return if the door is opening."""
        if self._optimistic_state is None:
            return False
        return self._optimistic_state

    @property
    def is_closing(self) -> bool | None:
        """Return if the door is closing."""
        if self._optimistic_state is None:
            return False
        return not self._optimistic_state

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door."""
        self._optimistic_state = True
        self.async_write_ha_state()
        try:
            await self._async_send_command(
                self.coordinator.client.trigger_auto_door(
                    device_id=self.coordinator.device_id,
                    zone_id=self._zone_id,
                    value=True,
                )
            )
        except HomeAssistantError:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door."""
        self._optimistic_state = False
        self.async_write_ha_state()
        try:
            await self._async_send_command(
                self.coordinator.client.trigger_auto_door(
                    device_id=self.coordinator.device_id,
                    zone_id=self._zone_id,
                    value=False,
                )
            )
        except HomeAssistantError:
            self._optimistic_state = None
            self.async_write_ha_state()
            raise
