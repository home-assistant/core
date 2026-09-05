"""Helpers for tracking HomeKit target selections."""

from collections.abc import Callable, Mapping
from fnmatch import fnmatchcase
import logging
from typing import Any, override

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    target as target_helper,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.typing import ConfigType

from .const import TARGET_CHANGE_RELOAD_COOLDOWN
from .util import state_needs_accessory_mode

_LOGGER = logging.getLogger(__name__)

_TARGET_PRIORITY = {
    ATTR_ENTITY_ID: 80,
    ATTR_DEVICE_ID: 70,
    ATTR_AREA_ID: 50,
    ATTR_FLOOR_ID: 40,
    ATTR_LABEL_ID: 30,
}
_ENTITY_GLOB_PRIORITY = 60
_DOMAIN_PRIORITY = 20
_UNKNOWN_TARGET_PRIORITY = 10
_NO_MATCH_PRIORITY = -1

type TargetEntityFilter = Callable[[HomeAssistant, str], bool]


@callback
def async_is_bridge_target_entity(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether a target entity can remain on a HomeKit bridge."""
    state = hass.states.get(entity_id)
    return state is None or not state_needs_accessory_mode(state)


@callback
def _async_filter_target_entity_ids(
    hass: HomeAssistant,
    entity_ids: set[str],
    entity_filter: TargetEntityFilter | None,
) -> set[str]:
    """Filter expanded target entities when requested."""
    if entity_filter is None:
        return entity_ids
    return {entity_id for entity_id in entity_ids if entity_filter(hass, entity_id)}


@callback
def async_target_entity_ids_by_type(
    hass: HomeAssistant,
    targets: Mapping[str, list[str]],
    *,
    entity_filter: TargetEntityFilter | None = None,
) -> dict[str, set[str]]:
    """Expand each target type separately to preserve match specificity."""
    expanded: dict[str, set[str]] = {}
    for target_type, target_ids in targets.items():
        if not target_ids:
            continue
        selected = target_helper.async_extract_referenced_entity_ids(
            hass, TargetSelection({target_type: target_ids})
        )
        expanded[target_type] = _async_filter_target_entity_ids(
            hass,
            selected.referenced | selected.indirectly_referenced,
            entity_filter,
        )
    return expanded


def _target_match_priority(
    entity_id: str, expanded_targets: Mapping[str, set[str]]
) -> int:
    """Return the most specific target type matching an entity."""
    return max(
        (
            _TARGET_PRIORITY.get(target_type, _UNKNOWN_TARGET_PRIORITY)
            for target_type, entity_ids in expanded_targets.items()
            if entity_id in entity_ids
        ),
        default=_NO_MATCH_PRIORITY,
    )


def _base_filter_match_priority(
    entity_id: str, filter_config: Mapping[str, Any], *, include: bool
) -> int:
    """Return the most specific base filter rule matching an entity."""
    if include:
        entities_key = CONF_INCLUDE_ENTITIES
        globs_key = CONF_INCLUDE_ENTITY_GLOBS
        domains_key = CONF_INCLUDE_DOMAINS
    else:
        entities_key = CONF_EXCLUDE_ENTITIES
        globs_key = CONF_EXCLUDE_ENTITY_GLOBS
        domains_key = CONF_EXCLUDE_DOMAINS

    if entity_id in filter_config.get(entities_key, []):
        return _TARGET_PRIORITY[ATTR_ENTITY_ID]
    if any(
        fnmatchcase(entity_id, pattern) for pattern in filter_config.get(globs_key, [])
    ):
        return _ENTITY_GLOB_PRIORITY
    if entity_id.partition(".")[0] in filter_config.get(domains_key, []):
        return _DOMAIN_PRIORITY
    return _NO_MATCH_PRIORITY


def should_include_entity(
    entity_id: str,
    filter_config: Mapping[str, Any],
    included_targets: Mapping[str, set[str]],
    excluded_targets: Mapping[str, set[str]],
    has_include_rules: bool,
) -> bool:
    """Resolve include and exclude rules by specificity."""
    include_target_priority = _target_match_priority(entity_id, included_targets)
    exclude_target_priority = _target_match_priority(entity_id, excluded_targets)
    include_priority = max(
        _base_filter_match_priority(entity_id, filter_config, include=True),
        include_target_priority,
    )
    exclude_priority = max(
        _base_filter_match_priority(entity_id, filter_config, include=False),
        exclude_target_priority,
    )
    if include_priority == exclude_priority:
        if include_priority == _NO_MATCH_PRIORITY:
            return not has_include_rules
        return (
            include_target_priority != include_priority
            and exclude_target_priority != exclude_priority
        )
    return include_priority > exclude_priority


# This functionality should move into the core target tracker in a later PR.
class HomeKitTargetEntitySetChangeTracker(TargetEntityChangeTracker):
    """Track changes to the entities referenced by a HomeKit target."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        action: Callable[[set[str], set[str]], Any],
        *,
        entity_filter: TargetEntityFilter | None,
    ) -> None:
        """Initialize the target entity set change tracker."""
        super().__init__(
            hass,
            target_selection,
            lambda entity_ids: _async_filter_target_entity_ids(
                hass, entity_ids, entity_filter
            ),
        )
        self._action = action
        self._tracked_entities: set[str] = set()
        self._group_entity_ids: set[str] = set()
        self._group_state_unsub: CALLBACK_TYPE | None = None
        self._refresh_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=TARGET_CHANGE_RELOAD_COOLDOWN,
            immediate=False,
            function=self._async_refresh,
        )

    @override
    async def async_setup(self) -> CALLBACK_TYPE:
        """Set up tracking without reporting the initial entity set as a change."""
        self._setup_selective_registry_listeners()
        self._async_update_group_state_listener()
        self._tracked_entities = self._referenced_entities()

        @callback
        def _async_unsubscribe() -> None:
            self._refresh_debouncer.async_shutdown()
            self._unsubscribe()

        return _async_unsubscribe

    @callback
    @override
    def _referenced_entities(self) -> set[str]:
        """Return the currently tracked entities, expanding groups."""
        selected = target_helper.async_extract_referenced_entity_ids(
            self._hass,
            self._target_selection,
            primary_entities_only=self._primary_entities_only,
        )
        return self._entity_filter(selected.referenced | selected.indirectly_referenced)

    @callback
    def _async_refresh(self) -> None:
        """Refresh the entities referenced by this target."""
        self._handle_entities_update(self._referenced_entities())

    @callback
    def _async_update_group_state_listener(self) -> None:
        """Track target groups and their nested groups."""
        group_entity_ids: set[str] = set()
        pending_entity_ids = list(self._target_selection.entity_ids)
        while pending_entity_ids:
            entity_id = pending_entity_ids.pop()
            state = self._hass.states.get(entity_id)
            if state is None:
                if entity_id.startswith("group."):
                    group_entity_ids.add(entity_id)
                continue
            member_entity_ids = state.attributes.get(ATTR_ENTITY_ID)
            if not isinstance(member_entity_ids, list):
                continue
            group_entity_ids.add(entity_id)
            pending_entity_ids.extend(
                member_entity_id
                for member_entity_id in member_entity_ids
                if member_entity_id not in group_entity_ids
            )

        if group_entity_ids == self._group_entity_ids:
            return

        old_unsub = self._group_state_unsub
        self._group_entity_ids = group_entity_ids
        self._group_state_unsub = async_track_state_change_event(
            self._hass, group_entity_ids, self._handle_group_state_change
        )
        if old_unsub:
            old_unsub()

    @callback
    def _handle_group_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Refresh when a target group's membership changes."""
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        old_members = old_state and old_state.attributes.get(ATTR_ENTITY_ID)
        new_members = new_state and new_state.attributes.get(ATTR_ENTITY_ID)
        if old_members == new_members:
            return
        self._async_update_group_state_listener()
        self._refresh_debouncer.async_schedule_call()

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
        if not (
            target.device_ids or target.area_ids or target.floor_ids or target.label_ids
        ):
            return False
        action: str = event.data["action"]
        if action != "update":
            return action != "reorder"
        if target.device_ids:
            # Direct device targets include child and split-device topology.
            return True

        changed_fields = set(event.data["changes"])
        relevant_fields = {"area_id"}
        if target.label_ids:
            relevant_fields.add("labels")
        return not relevant_fields.isdisjoint(changed_fields)

    @callback
    def _handle_entity_registry_update(self, event: Event[Any]) -> None:
        """Handle a relevant entity registry update."""
        if self._entity_registry_event_affects_target(event):
            self._refresh_debouncer.async_schedule_call()

    @callback
    def _handle_device_registry_update(self, event: Event[Any]) -> None:
        """Handle a relevant device registry update."""
        if self._device_registry_event_affects_target(event):
            self._refresh_debouncer.async_schedule_call()

    @callback
    def _handle_area_registry_update(self, _event: Event[Any]) -> None:
        """Handle an area registry update."""
        self._refresh_debouncer.async_schedule_call()

    @override
    @callback
    def _unsubscribe(self) -> None:
        """Unsubscribe from registry and group state changes."""
        super()._unsubscribe()
        if self._group_state_unsub:
            self._group_state_unsub()
            self._group_state_unsub = None

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
        if target.device_ids or target.area_ids or target.floor_ids or target.label_ids:
            self._registry_unsubs.append(
                self._hass.bus.async_listen(
                    dr.EVENT_DEVICE_REGISTRY_UPDATED,
                    self._handle_device_registry_update,
                )
            )
        if target.area_ids or target.floor_ids or target.label_ids:
            # Area update events do not report which fields changed.
            self._registry_unsubs.append(
                self._hass.bus.async_listen(
                    ar.EVENT_AREA_REGISTRY_UPDATED,
                    self._handle_area_registry_update,
                )
            )


async def async_track_target_entity_change(
    hass: HomeAssistant,
    target_config: ConfigType,
    action: Callable[[set[str], set[str]], Any],
    *,
    entity_filter: TargetEntityFilter | None = None,
) -> CALLBACK_TYPE:
    """Track changes to the entities referenced by a HomeKit target."""
    target_selection = TargetSelection(target_config)
    if not target_selection.has_any_target:
        raise HomeAssistantError(
            f"Target selection {target_config} does not contain any targets"
        )
    tracker = HomeKitTargetEntitySetChangeTracker(
        hass,
        target_selection,
        action,
        entity_filter=entity_filter,
    )
    return await tracker.async_setup()
