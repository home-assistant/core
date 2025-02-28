"""Event platform for Bring integration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from bring_api import ActivityType, BringList

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BringConfigEntry
from .coordinator import BringActivityCoordinator
from .entity import BringBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    coordinator = config_entry.runtime_data
    lists_added: set[str] = set()

    @callback
    def add_entities() -> None:
        """Add event entities."""
        nonlocal lists_added

        if new_lists := {lst.listUuid for lst in coordinator.data.lists} - lists_added:
            async_add_entities(
                BringEventEntity(
                    coordinator.activity,
                    bring_list,
                )
                for bring_list in coordinator.data.lists
                if bring_list.listUuid in new_lists
            )
            lists_added |= new_lists

    coordinator.activity.async_add_listener(add_entities)
    add_entities()


class BringEventEntity(BringBaseEntity, EventEntity):
    """An event entity."""

    _attr_translation_key = "activities"
    coordinator: BringActivityCoordinator

    def __init__(
        self,
        coordinator: BringActivityCoordinator,
        bring_list: BringList,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, bring_list)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{self._list_uuid}_activities"
        )
        self._attr_event_types = [event.name.lower() for event in ActivityType]

    def _async_handle_event(self) -> None:
        """Handle the activity event."""
        bring_list = self.coordinator.data[self._list_uuid]
        last_event_triggered = self.state
        if bring_list.activity.timeline and (
            last_event_triggered is None
            or datetime.fromisoformat(last_event_triggered)
            < bring_list.activity.timestamp
        ):
            activity = bring_list.activity.timeline[0]
            attributes = asdict(activity.content)

            attributes["last_activity_by"] = next(
                (
                    x.name
                    for x in bring_list.users.users
                    if x.publicUuid == activity.content.publicUserUuid
                ),
                None,
            )

            self._trigger_event(
                activity.type.name.lower(),
                attributes,
            )
            self.async_write_ha_state()

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return (
            f"https://api.getbring.com/rest/v2/bringusers/profilepictures/{public_uuid}"
            if (public_uuid := self.state_attributes.get("publicUserUuid"))
            else super().entity_picture
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""
        await super().async_added_to_hass()
        self._async_handle_event()

    def _handle_coordinator_update(self) -> None:
        self._async_handle_event()
        return super()._handle_coordinator_update()
