"""Helpers for tracking HomeKit target selections."""

from collections.abc import Callable
from typing import Any, override

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.typing import ConfigType


class HomeKitTargetEntitySetChangeTracker(TargetEntityChangeTracker):
    """Track changes to the entities referenced by a HomeKit target."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        action: Callable[[set[str], set[str]], Any],
    ) -> None:
        """Initialize the target entity set change tracker."""
        super().__init__(hass, target_selection, lambda entity_ids: entity_ids)
        self._action = action
        self._tracked_entities: set[str] = set()

    @override
    async def async_setup(self) -> CALLBACK_TYPE:
        """Set up tracking without reporting the initial entity set as a change."""
        self._setup_selective_registry_listeners()
        self._tracked_entities = self._referenced_entities()
        return self._unsubscribe

    @callback
    @override
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Report additions and removals from the targeted entity set."""
        previous_entities = self._tracked_entities
        self._tracked_entities = tracked_entities
        added = tracked_entities - previous_entities
        removed = previous_entities - tracked_entities
        if added or removed:
            self._action(added, removed)

    @callback
    def _entity_registry_event_affects_target(self, event: Event[Any]) -> bool:
        """Return whether an entity registry event can change this target."""
        target = self._target_selection
        if not (
            target.device_ids or target.area_ids or target.floor_ids or target.label_ids
        ):
            return False
        action: str = event.data["action"]
        if action != "update":
            return action != "reorder"
        if "old_entity_id" in event.data:
            return True

        changed_fields = set(event.data["changes"])
        relevant_fields = {"entity_category", "hidden_by"}
        if target.device_ids:
            relevant_fields.add("device_id")
        if target.area_ids or target.floor_ids or target.label_ids:
            relevant_fields.update(("area_id", "device_id"))
        if target.label_ids:
            relevant_fields.add("labels")
        return not relevant_fields.isdisjoint(changed_fields)

    @callback
    def _device_registry_event_affects_target(self, event: Event[Any]) -> bool:
        """Return whether a device registry event can change this target."""
        target = self._target_selection
        if not (target.area_ids or target.floor_ids or target.label_ids):
            return False
        action: str = event.data["action"]
        if action != "update":
            return action != "reorder"

        changed_fields = set(event.data["changes"])
        relevant_fields = {"area_id"}
        if target.label_ids:
            relevant_fields.add("labels")
        return not relevant_fields.isdisjoint(changed_fields)

    @callback
    def _handle_entity_registry_update(self, event: Event[Any]) -> None:
        """Handle a relevant entity registry update."""
        if self._entity_registry_event_affects_target(event):
            self._handle_target_update(event)

    @callback
    def _handle_device_registry_update(self, event: Event[Any]) -> None:
        """Handle a relevant device registry update."""
        if self._device_registry_event_affects_target(event):
            self._handle_target_update(event)

    def _setup_selective_registry_listeners(self) -> None:
        """Set up listeners for registries used by this target selection."""
        target = self._target_selection
        if target.device_ids or target.area_ids or target.floor_ids or target.label_ids:
            self._registry_unsubs.append(
                self._hass.bus.async_listen(
                    er.EVENT_ENTITY_REGISTRY_UPDATED,
                    self._handle_entity_registry_update,
                )
            )
        if target.area_ids or target.floor_ids or target.label_ids:
            self._registry_unsubs.append(
                self._hass.bus.async_listen(
                    dr.EVENT_DEVICE_REGISTRY_UPDATED,
                    self._handle_device_registry_update,
                )
            )
            # Area update events do not report which fields changed.
            self._registry_unsubs.append(
                self._hass.bus.async_listen(
                    ar.EVENT_AREA_REGISTRY_UPDATED, self._handle_target_update
                )
            )


async def async_track_target_entity_change(
    hass: HomeAssistant,
    target_config: ConfigType,
    action: Callable[[set[str], set[str]], Any],
) -> CALLBACK_TYPE:
    """Track changes to the entities referenced by a HomeKit target."""
    target_selection = TargetSelection(target_config)
    if not target_selection.has_any_target:
        raise HomeAssistantError(
            f"Target selection {target_config} does not contain any targets"
        )
    tracker = HomeKitTargetEntitySetChangeTracker(hass, target_selection, action)
    return await tracker.async_setup()
