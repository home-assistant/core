"""Provide entity classes for group entities."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Collection, Mapping
import logging
from typing import Any

from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers import start
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event

from .const import ATTR_AUTO, ATTR_ORDER, DOMAIN, GROUP_ORDER, REG_KEY
from .registry import GroupIntegrationRegistry, SingleStateType

ENTITY_ID_FORMAT = DOMAIN + ".{}"

_PACKAGE_LOGGER = logging.getLogger(__package__)

_LOGGER = logging.getLogger(__name__)


class GroupEntity(Entity):
    """Representation of a Group of entities."""

    _unrecorded_attributes = frozenset({ATTR_ENTITY_ID})

    _attr_should_poll = False
    _entity_ids: list[str]

    @callback
    def async_start_preview(
        self,
        preview_callback: Callable[[str, Mapping[str, Any]], None],
    ) -> CALLBACK_TYPE:
        """Render a preview."""

        for entity_id in self._entity_ids:
            if (state := self.hass.states.get(entity_id)) is None:
                continue
            self.async_update_supported_features(entity_id, state)

        @callback
        def async_state_changed_listener(
            event: Event[EventStateChangedData] | None,
        ) -> None:
            """Handle child updates."""
            self.async_update_group_state()
            if event:
                self.async_update_supported_features(
                    event.data["entity_id"], event.data["new_state"]
                )
            calculated_state = self._async_calculate_state()
            preview_callback(calculated_state.state, calculated_state.attributes)

        async_state_changed_listener(None)
        return async_track_state_change_event(
            self.hass, self._entity_ids, async_state_changed_listener
        )

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        for entity_id in self._entity_ids:
            if (state := self.hass.states.get(entity_id)) is None:
                continue
            self.async_update_supported_features(entity_id, state)

        @callback
        def async_state_changed_listener(
            event: Event[EventStateChangedData],
        ) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_update_supported_features(
                event.data["entity_id"], event.data["new_state"]
            )
            self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )
        self.async_on_remove(start.async_at_start(self.hass, self._update_at_start))

    @callback
    def _update_at_start(self, _: HomeAssistant) -> None:
        """Update the group state at start."""
        self.async_update_group_state()
        self.async_write_ha_state()

    @callback
    def async_defer_or_update_ha_state(self) -> None:
        """Only update once at start."""
        if not self.hass.is_running:
            return

        self.async_update_group_state()
        self.async_write_ha_state()

    @abstractmethod
    @callback
    def async_update_group_state(self) -> None:
        """Abstract method to update the entity."""

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""


class Group(Entity):
    """Track a group of entity ids."""

    _unrecorded_attributes = frozenset({ATTR_ENTITY_ID, ATTR_ORDER, ATTR_AUTO})

    _attr_should_poll = False
    tracking: tuple[str, ...]
    trackable: tuple[str, ...]
    single_state_type_key: SingleStateType | None

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        *,
        created_by_service: bool,
        entity_ids: Collection[str] | None,
        icon: str | None,
        mode: bool | None,
        order: int | None,
    ) -> None:
        """Initialize a group.

        This Object has factory function for creation.
        """
        self.hass = hass
        self._attr_name = name
        self._state: str | None = None
        self._attr_icon = icon
        self._entity_ids = entity_ids
        self._on_off: dict[str, bool] = {}
        self._assumed: dict[str, bool] = {}
        self._on_states: set[str] = set()
        self.created_by_service = created_by_service
        self.mode = any
        if mode:
            self.mode = all
        self._order = order
        self._assumed_state = False
        self._async_unsub_state_changed: CALLBACK_TYPE | None = None

    @staticmethod
    @callback
    def async_create_group_entity(
        hass: HomeAssistant,
        name: str,
        *,
        created_by_service: bool,
        entity_ids: Collection[str] | None,
        icon: str | None,
        mode: bool | None,
        object_id: str | None,
        order: int | None,
    ) -> Group:
        """Create a group entity."""
        if order is None:
            hass.data.setdefault(GROUP_ORDER, 0)
            order = hass.data[GROUP_ORDER]
            # Keep track of the group order without iterating
            # every state in the state machine every time
            # we setup a new group
            hass.data[GROUP_ORDER] += 1

        group = Group(
            hass,
            name,
            created_by_service=created_by_service,
            entity_ids=entity_ids,
            icon=icon,
            mode=mode,
            order=order,
        )

        group.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id or name, hass=hass
        )

        return group

    @staticmethod
    async def async_create_group(
        hass: HomeAssistant,
        name: str,
        *,
        created_by_service: bool,
        entity_ids: Collection[str] | None,
        icon: str | None,
        mode: bool | None,
        object_id: str | None,
        order: int | None,
    ) -> Group:
        """Initialize a group.

        This method must be run in the event loop.
        """
        group = Group.async_create_group_entity(
            hass,
            name,
            created_by_service=created_by_service,
            entity_ids=entity_ids,
            icon=icon,
            mode=mode,
            object_id=object_id,
            order=order,
        )

        # If called before the platform async_setup is called (test cases)
        await async_get_component(hass).async_add_entities([group])
        return group

    def set_name(self, value: str) -> None:
        """Set Group name."""
        self._attr_name = value

    @property
    def state(self) -> str | None:
        """Return the state of the group."""
        return self._state

    def set_icon(self, value: str | None) -> None:
        """Set Icon for group."""
        self._attr_icon = value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes for the group."""
        data = {ATTR_ENTITY_ID: self.tracking, ATTR_ORDER: self._order}
        if self.created_by_service:
            data[ATTR_AUTO] = True

        return data

    @property
    def assumed_state(self) -> bool:
        """Test if any member has an assumed state."""
        return self._assumed_state

    def update_tracked_entity_ids(self, entity_ids: Collection[str] | None) -> None:
        """Update the member entity IDs."""
        asyncio.run_coroutine_threadsafe(
            self.async_update_tracked_entity_ids(entity_ids), self.hass.loop
        ).result()

    async def async_update_tracked_entity_ids(
        self, entity_ids: Collection[str] | None
    ) -> None:
        """Update the member entity IDs.

        This method must be run in the event loop.
        """
        self._async_stop()
        self._set_tracked(entity_ids)
        self._reset_tracked_state()
        self._async_start()

    def _set_tracked(self, entity_ids: Collection[str] | None) -> None:
        """Tuple of entities to be tracked."""
        # tracking are the entities we want to track
        # trackable are the entities we actually watch

        if not entity_ids:
            self.tracking = ()
            self.trackable = ()
            self.single_state_type_key = None
            return

        registry: GroupIntegrationRegistry = self.hass.data[REG_KEY]
        excluded_domains = registry.exclude_domains

        tracking: list[str] = []
        trackable: list[str] = []
        single_state_type_set: set[SingleStateType] = set()
        for ent_id in entity_ids:
            ent_id_lower = ent_id.lower()
            domain = split_entity_id(ent_id_lower)[0]
            tracking.append(ent_id_lower)
            if domain not in excluded_domains:
                trackable.append(ent_id_lower)
            if domain in registry.state_group_mapping:
                single_state_type_set.add(registry.state_group_mapping[domain])
            elif domain == DOMAIN:
                # If a group contains another group we check if that group
                # has a specific single state type
                if ent_id in registry.state_group_mapping:
                    single_state_type_set.add(registry.state_group_mapping[ent_id])
            else:
                single_state_type_set.add(SingleStateType(STATE_ON, STATE_OFF))

        if len(single_state_type_set) == 1:
            self.single_state_type_key = next(iter(single_state_type_set))
            # To support groups with nested groups we store the state type
            # per group entity_id if there is a single state type
            registry.state_group_mapping[self.entity_id] = self.single_state_type_key
        else:
            self.single_state_type_key = None
        self.async_on_remove(self._async_deregister)

        self.trackable = tuple(trackable)
        self.tracking = tuple(tracking)

    @callback
    def _async_deregister(self) -> None:
        """Deregister group entity from the registry."""
        registry: GroupIntegrationRegistry = self.hass.data[REG_KEY]
        if self.entity_id in registry.state_group_mapping:
            registry.state_group_mapping.pop(self.entity_id)

    @callback
    def _async_start(self, _: HomeAssistant | None = None) -> None:
        """Start tracking members and write state."""
        self._reset_tracked_state()
        self._async_start_tracking()
        self.async_write_ha_state()

    @callback
    def _async_start_tracking(self) -> None:
        """Start tracking members.

        This method must be run in the event loop.
        """
        if self.trackable and self._async_unsub_state_changed is None:
            self._async_unsub_state_changed = async_track_state_change_event(
                self.hass, self.trackable, self._async_state_changed_listener
            )

        self._async_update_group_state()

    @callback
    def _async_stop(self) -> None:
        """Unregister the group from Home Assistant.

        This method must be run in the event loop.
        """
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine current group state."""
        self._state = None
        self._async_update_group_state()

    async def async_added_to_hass(self) -> None:
        """Handle addition to Home Assistant."""
        self._set_tracked(self._entity_ids)
        self.async_on_remove(start.async_at_start(self.hass, self._async_start))

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal from Home Assistant."""
        self._async_stop()

    async def _async_state_changed_listener(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Respond to a member state changing.

        This method must be run in the event loop.
        """
        # removed
        if self._async_unsub_state_changed is None:
            return

        self.async_set_context(event.context)

        if (new_state := event.data["new_state"]) is None:
            # The state was removed from the state machine
            self._reset_tracked_state()

        self._async_update_group_state(new_state)
        self.async_write_ha_state()

    def _reset_tracked_state(self) -> None:
        """Reset tracked state."""
        self._on_off = {}
        self._assumed = {}
        self._on_states = set()

        for entity_id in self.trackable:
            if (state := self.hass.states.get(entity_id)) is not None:
                self._see_state(state)

    def _see_state(self, new_state: State) -> None:
        """Keep track of the state."""
        entity_id = new_state.entity_id
        domain = new_state.domain
        state = new_state.state
        registry: GroupIntegrationRegistry = self.hass.data[REG_KEY]
        self._assumed[entity_id] = bool(new_state.attributes.get(ATTR_ASSUMED_STATE))

        if domain not in registry.on_states_by_domain:
            # Handle the group of a group case
            if state in registry.on_off_mapping:
                self._on_states.add(state)
            elif state in registry.off_on_mapping:
                self._on_states.add(registry.off_on_mapping[state])
            self._on_off[entity_id] = state in registry.on_off_mapping
        else:
            entity_on_state = registry.on_states_by_domain[domain]
            if domain in registry.on_states_by_domain:
                self._on_states.update(entity_on_state)
            self._on_off[entity_id] = state in entity_on_state

    @callback
    def _async_update_group_state(self, tr_state: State | None = None) -> None:
        """Update group state.

        Optionally you can provide the only state changed since last update
        allowing this method to take shortcuts.

        This method must be run in the event loop.
        """
        # To store current states of group entities. Might not be needed.
        if tr_state:
            self._see_state(tr_state)

        if not self._on_off:
            return

        if (
            tr_state is None
            or self._assumed_state
            and not tr_state.attributes.get(ATTR_ASSUMED_STATE)
        ):
            self._assumed_state = self.mode(self._assumed.values())

        elif tr_state.attributes.get(ATTR_ASSUMED_STATE):
            self._assumed_state = True

        num_on_states = len(self._on_states)
        # If all the entity domains we are tracking
        # have the same on state we use this state
        # and its hass.data[REG_KEY].on_off_mapping to off
        if num_on_states == 1:
            on_state = next(iter(self._on_states))
        # If we do not have an on state for any domains
        # we use None (which will be STATE_UNKNOWN)
        elif num_on_states == 0:
            self._state = None
            return
        if self.single_state_type_key:
            on_state = self.single_state_type_key.on_state
        # If the entity domains have more than one
        # on state, we use STATE_ON/STATE_OFF
        else:
            on_state = STATE_ON
        group_is_on = self.mode(self._on_off.values())
        if group_is_on:
            self._state = on_state
        elif self.single_state_type_key:
            self._state = self.single_state_type_key.off_state
        else:
            self._state = STATE_OFF


def async_get_component(hass: HomeAssistant) -> EntityComponent[Group]:
    """Get the group entity component."""
    if (component := hass.data.get(DOMAIN)) is None:
        component = hass.data[DOMAIN] = EntityComponent[Group](
            _PACKAGE_LOGGER, DOMAIN, hass
        )
    return component
