"""Helpers for dealing with entity targets."""

import abc
import asyncio
from collections.abc import Callable, Coroutine, Mapping
import dataclasses
import logging
from logging import Logger
from typing import Any, TypeGuard, override

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ENTITY_MATCH_NONE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError

from . import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    group,
    label_registry as lr,
)
from .deprecation import deprecated_class
from .event import async_track_state_change_event
from .typing import ConfigType

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True, frozen=True)
class TargetStateChangedData:
    """Data for state change events related to targets.

    `targeted_entity_states` holds the states of all targeted entities as of
    the state change event. State change events are dispatched one event loop
    iteration after the state machine is updated, so the live state machine
    may already contain later changes; this mapping does not. It is only
    valid during the synchronous callback: it is updated in place as
    subsequent events are dispatched.
    """

    state_change_event: Event[EventStateChangedData]
    targeted_entity_ids: set[str]
    targeted_entity_states: Mapping[str, State | None]


def _has_match(ids: str | list[str] | None) -> TypeGuard[str | list[str]]:
    """Check if ids can match anything."""
    return ids not in (None, ENTITY_MATCH_NONE)


class TargetSelection:
    """Class to represent target selection."""

    __slots__ = ("area_ids", "device_ids", "entity_ids", "floor_ids", "label_ids")

    def __init__(self, config: ConfigType) -> None:
        """Extract ids from the config."""
        entity_ids: str | list | None = config.get(ATTR_ENTITY_ID)
        device_ids: str | list | None = config.get(ATTR_DEVICE_ID)
        area_ids: str | list | None = config.get(ATTR_AREA_ID)
        floor_ids: str | list | None = config.get(ATTR_FLOOR_ID)
        label_ids: str | list | None = config.get(ATTR_LABEL_ID)

        self.entity_ids = (
            set(cv.ensure_list(entity_ids)) if _has_match(entity_ids) else set()
        )
        self.device_ids = (
            set(cv.ensure_list(device_ids)) if _has_match(device_ids) else set()
        )
        self.area_ids = set(cv.ensure_list(area_ids)) if _has_match(area_ids) else set()
        self.floor_ids = (
            set(cv.ensure_list(floor_ids)) if _has_match(floor_ids) else set()
        )
        self.label_ids = (
            set(cv.ensure_list(label_ids)) if _has_match(label_ids) else set()
        )

    @property
    def has_any_target(self) -> bool:
        """Determine if any target is present."""
        return bool(
            self.entity_ids
            or self.device_ids
            or self.area_ids
            or self.floor_ids
            or self.label_ids
        )


@deprecated_class("TargetSelection", breaks_in_ha_version="2026.12.0")
class TargetSelectorData(TargetSelection):
    """Class to represent target selector data."""

    @property
    def has_any_selector(self) -> bool:
        """Determine if any selectors are present."""
        return super().has_any_target


@dataclasses.dataclass(slots=True)
class SelectedEntities:
    """Class to hold the selected entities."""

    # Entity IDs of entities that were explicitly mentioned.
    referenced: set[str] = dataclasses.field(default_factory=set)

    # Entity IDs of entities that were referenced via device/area/floor/label ID.
    # Should not trigger a warning when they don't exist.
    indirectly_referenced: set[str] = dataclasses.field(default_factory=set)

    # Referenced items that could not be found.
    missing_devices: set[str] = dataclasses.field(default_factory=set)
    missing_areas: set[str] = dataclasses.field(default_factory=set)
    missing_floors: set[str] = dataclasses.field(default_factory=set)
    missing_labels: set[str] = dataclasses.field(default_factory=set)

    referenced_devices: set[str] = dataclasses.field(default_factory=set)
    referenced_areas: set[str] = dataclasses.field(default_factory=set)

    def log_missing(self, missing_entities: set[str], logger: Logger) -> None:
        """Log about missing items."""
        parts = []
        for label, items in (
            ("floors", self.missing_floors),
            ("areas", self.missing_areas),
            ("devices", self.missing_devices),
            ("entities", missing_entities),
            ("labels", self.missing_labels),
        ):
            if items:
                parts.append(f"{label} {', '.join(sorted(items))}")

        if not parts:
            return

        logger.warning(
            "Referenced %s are missing or not currently available",
            ", ".join(parts),
        )


def async_extract_referenced_entity_ids(
    hass: HomeAssistant,
    target_selection: TargetSelection,
    expand_group: bool = True,
    *,
    primary_entities_only: bool = True,
) -> SelectedEntities:
    """Extract referenced entity IDs from a target selection.

    When `primary_entities_only` is True (the default), entities with an
    `entity_category` (i.e. config or diagnostic entities) are excluded from
    indirect expansion via device, area, and floor. When False, those entities
    are included. Direct label-to-entity expansion is unaffected by this flag.
    Label targeting via labeled devices or areas follows the same filtering
    rules as other indirect device/area expansion paths: filtered when
    `primary_entities_only` is True, and included when it is False.
    """
    selected = SelectedEntities()

    if not target_selection.has_any_target:
        return selected

    entity_ids: set[str] | list[str] = target_selection.entity_ids
    if expand_group:
        entity_ids = group.expand_entity_ids(hass, entity_ids)

    selected.referenced.update(entity_ids)

    if (
        not target_selection.device_ids
        and not target_selection.area_ids
        and not target_selection.floor_ids
        and not target_selection.label_ids
    ):
        return selected

    entities = er.async_get(hass).entities
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    if target_selection.floor_ids:
        floor_reg = fr.async_get(hass)
        for floor_id in target_selection.floor_ids:
            if floor_id not in floor_reg.floors:
                selected.missing_floors.add(floor_id)

    for area_id in target_selection.area_ids:
        if area_id not in area_reg.areas:
            selected.missing_areas.add(area_id)

    for device_id in target_selection.device_ids:
        if device_id in dev_reg.devices:
            selected.referenced_devices.add(device_id)
        elif split_devices := dev_reg.async_get_devices_for_composite_device_id(
            device_id
        ):
            # A multi config entry composite device id is no longer a device itself;
            # it resolves to the devices it was split into so actions targeting it
            # still trickle down. Only the splits are referenced, not the composite id,
            # so a device-id consumer does not act on the same underlying device twice.
            selected.referenced_devices.update(device.id for device in split_devices)
        else:
            selected.missing_devices.add(device_id)
            selected.referenced_devices.add(device_id)

    if target_selection.label_ids:
        label_reg = lr.async_get(hass)
        for label_id in target_selection.label_ids:
            if label_id not in label_reg.labels:
                selected.missing_labels.add(label_id)

            for entity_entry in entities.get_entries_for_label(label_id):
                if entity_entry.hidden_by is None:
                    selected.indirectly_referenced.add(entity_entry.entity_id)

            for device_entry in dev_reg.devices.get_devices_for_label(label_id):
                selected.referenced_devices.add(device_entry.id)

            for area_entry in area_reg.areas.get_areas_for_label(label_id):
                selected.referenced_areas.add(area_entry.id)

    # Find areas for targeted floors
    if target_selection.floor_ids:
        selected.referenced_areas.update(
            area_entry.id
            for floor_id in target_selection.floor_ids
            for area_entry in area_reg.areas.get_areas_for_floor(floor_id)
        )

    selected.referenced_areas.update(target_selection.area_ids)

    if not selected.referenced_areas and not selected.referenced_devices:
        return selected

    def _include_entry(entry: er.RegistryEntry) -> bool:
        """Return True if the entry should be included in indirect expansion."""
        if entry.hidden_by is not None:
            return False
        return not primary_entities_only or entry.entity_category is None

    # Add indirectly referenced by device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in selected.referenced_devices
        for entry in entities.get_entries_for_device_id(device_id)
        if _include_entry(entry)
    )

    # Find devices for targeted areas
    referenced_devices_by_area: set[str] = set()
    if selected.referenced_areas:
        for area_id in selected.referenced_areas:
            referenced_devices_by_area.update(
                device_entry.id
                for device_entry in dev_reg.devices.get_devices_for_area_id(area_id)
            )
    selected.referenced_devices.update(referenced_devices_by_area)

    # Add indirectly referenced by area
    selected.indirectly_referenced.update(
        entry.entity_id
        for area_id in selected.referenced_areas
        # The entity's area matches a targeted area
        for entry in entities.get_entries_for_area_id(area_id)
        if _include_entry(entry)
    )
    # Add indirectly referenced by area through device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in referenced_devices_by_area
        for entry in entities.get_entries_for_device_id(device_id)
        # The entity's device matches a device referenced by an area and the
        # entity has no explicitly set area.
        if _include_entry(entry) and not entry.area_id
    )

    return selected


class TargetEntityChangeTracker(abc.ABC):
    """Helper class to manage entity change tracking for targets."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        entity_filter: Callable[[set[str]], set[str]],
        *,
        primary_entities_only: bool = True,
    ) -> None:
        """Initialize the state change tracker."""
        self._hass = hass
        self._target_selection = target_selection
        self._entity_filter = entity_filter
        self._primary_entities_only = primary_entities_only

        self._registry_unsubs: list[CALLBACK_TYPE] = []

    async def async_setup(self) -> Callable[[], None]:
        """Set up the state change tracking."""
        self._setup_registry_listeners()
        self._handle_target_update()
        return self._unsubscribe

    @abc.abstractmethod
    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Called when there's an update to tracked target entities."""

    @callback
    def _referenced_entities(self) -> set[str]:
        """Return the currently tracked, filtered entity ids."""
        selected = async_extract_referenced_entity_ids(
            self._hass,
            self._target_selection,
            expand_group=False,
            primary_entities_only=self._primary_entities_only,
        )
        return self._entity_filter(selected.referenced | selected.indirectly_referenced)

    @callback
    def _handle_target_update(self, event: Event[Any] | None = None) -> None:
        """Handle updates in the tracked targets."""
        self._handle_entities_update(self._referenced_entities())

    def _setup_registry_listeners(self) -> None:
        """Set up listeners for registry changes that require resubscription."""

        # Subscribe to registry updates that can change the entities to track:
        # - Entity registry: entity added/removed;
        #   entity labels changed; entity area changed.
        # - Device registry: device labels changed; device area changed.
        # - Area registry: area floor changed.
        #
        # We don't track other registries (like floor or label registries) because their
        # changes don't affect which entities are tracked.
        self._registry_unsubs = [
            self._hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_target_update
            ),
            self._hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._handle_target_update
            ),
            self._hass.bus.async_listen(
                ar.EVENT_AREA_REGISTRY_UPDATED, self._handle_target_update
            ),
        ]

    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        for registry_unsub in self._registry_unsubs:
            registry_unsub()
        self._registry_unsubs.clear()


class TargetStateChangeTracker(TargetEntityChangeTracker):
    """Helper class to manage state change tracking for targets."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        action: Callable[[TargetStateChangedData], Any],
        entity_filter: Callable[[set[str]], set[str]],
        on_entities_update: Callable[
            [set[str], set[str], Mapping[str, State | None]],
            Coroutine[Any, Any, None] | None,
        ]
        | None = None,
        *,
        primary_entities_only: bool = True,
    ) -> None:
        """Initialize the state change tracker.

        `on_entities_update` may be a plain callback or a coroutine function.
        It is called with the added and removed entity ids and the states of
        all currently targeted entities; the states mapping is only valid during
        the synchronous call, so a coroutine must copy what it needs before awaiting.
        """
        super().__init__(
            hass,
            target_selection,
            entity_filter,
            primary_entities_only=primary_entities_only,
        )
        self._action = action
        self._on_entities_update = on_entities_update
        self._state_change_unsub: CALLBACK_TYPE | None = None
        self._tracked_entities: set[str] = set()
        self._tracked_entity_states: dict[str, State | None] = {}
        self._update_tasks: set[asyncio.Task[None]] = set()

    @override
    async def async_setup(self) -> Callable[[], None]:
        """Set up tracking, awaiting the update for the initial entity set.

        The initial update is awaited so that a coroutine `on_entities_update`
        (e.g. one that loads history) completes before setup returns.
        """
        self._setup_registry_listeners()
        entities = self._referenced_entities()
        if (coro := self._apply_entities_update(entities)) is not None:
            await coro
        return self._unsubscribe

    @callback
    @override
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Handle a registry-driven change to the tracked entity set."""
        if (coro := self._apply_entities_update(tracked_entities)) is None:
            return
        # Tracked so it can be cancelled on unsubscribe.
        task = self._hass.async_create_background_task(
            coro, "Target entity tracker update"
        )
        self._update_tasks.add(task)
        task.add_done_callback(self._update_tasks.discard)

    def _apply_entities_update(
        self, tracked_entities: set[str]
    ) -> Coroutine[Any, Any, None] | None:
        """Resubscribe to state changes; return the update coroutine, if any."""
        previous_entities = self._tracked_entities
        self._tracked_entities = tracked_entities

        # Carry over the tracked states of still-tracked entities: they are
        # consistent with the already-dispatched event stream, while the live
        # state machine may be ahead of it. Only entities new to the view are
        # read from the live state machine.
        previous_states = self._tracked_entity_states
        tracked_entity_states = {
            entity_id: (
                previous_states[entity_id]
                if entity_id in previous_states
                else self._hass.states.get(entity_id)
            )
            for entity_id in tracked_entities
        }
        self._tracked_entity_states = tracked_entity_states

        result: Coroutine[Any, Any, None] | None = None
        if self._on_entities_update is not None:
            added = tracked_entities - previous_entities
            removed = previous_entities - tracked_entities
            if added or removed:
                result = self._on_entities_update(added, removed, tracked_entity_states)

        @callback
        def state_change_listener(event: Event[EventStateChangedData]) -> None:
            """Handle state change events."""
            if (entity_id := event.data["entity_id"]) not in tracked_entities:
                return
            tracked_entity_states[entity_id] = event.data["new_state"]
            self._action(
                TargetStateChangedData(event, tracked_entities, tracked_entity_states)
            )

        _LOGGER.debug("Tracking state changes for entities: %s", tracked_entities)
        # Subscribe before unsubscribing the previous listener: if this
        # tracker is the only subscriber, unsubscribing first tears down the
        # shared state change tracker, dropping events which have been fired
        # but not yet dispatched.
        previous_unsub = self._state_change_unsub
        self._state_change_unsub = async_track_state_change_event(
            self._hass, tracked_entities, state_change_listener
        )
        if previous_unsub:
            previous_unsub()
        return result

    @override
    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        super()._unsubscribe()
        if self._state_change_unsub:
            self._state_change_unsub()
            self._state_change_unsub = None
        for task in self._update_tasks:
            task.cancel()
        self._update_tasks.clear()


async def async_track_target_selector_state_change_event(
    hass: HomeAssistant,
    target_selector_config: ConfigType,
    action: Callable[[TargetStateChangedData], Any],
    entity_filter: Callable[[set[str]], set[str]] = lambda x: x,
    on_entities_update: Callable[
        [set[str], set[str], Mapping[str, State | None]],
        Coroutine[Any, Any, None] | None,
    ]
    | None = None,
    *,
    primary_entities_only: bool = True,
) -> CALLBACK_TYPE:
    """Track state changes for entities in a target selector.

    Tracks entities referenced directly or indirectly.
    When `primary_entities_only` is True, indirect target
    expansion (via device, area, and floor) skips entities
    with an `entity_category` (config or diagnostic entities).

    `on_entities_update` is called with the added and removed entity ids and
    the states of all currently targeted entities. It may be a coroutine
    function; The states mapping is only valid during the synchronous call.
    """
    target_selection = TargetSelection(target_selector_config)
    if not target_selection.has_any_target:
        raise HomeAssistantError(
            "Target selector"
            f" {target_selector_config}"
            " does not have any selectors defined"
        )
    tracker = TargetStateChangeTracker(
        hass,
        target_selection,
        action,
        entity_filter,
        on_entities_update,
        primary_entities_only=primary_entities_only,
    )
    return await tracker.async_setup()
