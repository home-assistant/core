"""Event platform for LinknLink eMotion Ultra target positions."""

from typing import override

from aiolinknlink import UltraPositionUpdate

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

EVENT_POSITION_UPDATE = "position_update"

POSITION_EVENT_DESCRIPTION = EventEntityDescription(
    key="target_position",
    translation_key="target_position",
    event_types=[EVENT_POSITION_UPDATE],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ultra target-position event entity."""
    async_add_entities(
        [LinknLinkPositionEvent(entry.runtime_data, POSITION_EVENT_DESCRIPTION)]
    )


class LinknLinkPositionEvent(LinknLinkEntity, EventEntity):
    """Publish each local UDP target-position update as an HA event entity."""

    entity_description: EventEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether the local UDP subscription is active."""
        state = self.coordinator.position_state
        return state is not None and state.subscribed

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to high-frequency target-position updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_position_listener(
                self._async_handle_position_update
            )
        )

    @callback
    def _async_handle_position_update(self, update: UltraPositionUpdate | None) -> None:
        """Publish a position event or update subscription availability."""
        if update is not None:
            self._trigger_event(
                EVENT_POSITION_UPDATE,
                {
                    "target_count": update.target_count,
                    "targets": [
                        {"x": target.x, "y": target.y, "z": target.z}
                        for target in update.targets
                    ],
                    "nearest_horizontal_distance": (update.nearest_horizontal_distance),
                    "nearest_distance": update.nearest_distance,
                },
            )
        self.async_write_ha_state()
