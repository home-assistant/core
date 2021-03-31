"""Provide the functionality to group entities."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from contextvars import ContextVar
import logging
from typing import Any, Iterable, List, cast

import voluptuous as vol

from homeassistant import core as ha
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_NAME,
    CONF_ENTITIES,
    CONF_ICON,
    CONF_NAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    EVENT_HOMEASSISTANT_START,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CoreState, HomeAssistant, callback, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.loader import bind_hass

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

DOMAIN = "group"
GROUP_ORDER = "group_order"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_ALL = "all"

ATTR_ADD_ENTITIES = "add_entities"
ATTR_AUTO = "auto"
ATTR_ENTITIES = "entities"
ATTR_OBJECT_ID = "object_id"
ATTR_ORDER = "order"
ATTR_ALL = "all"

SERVICE_SET = "set"
SERVICE_REMOVE = "remove"

PLATFORMS = ["light", "cover", "notify"]

REG_KEY = f"{DOMAIN}_registry"

_LOGGER = logging.getLogger(__name__)

current_domain: ContextVar[str] = ContextVar("current_domain")


def _conf_preprocess(value):
    """Preprocess alternative configuration formats."""
    if not isinstance(value, dict):
        value = {CONF_ENTITIES: value}

    return value


GROUP_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_ENTITIES): vol.Any(cv.entity_ids, None),
            CONF_NAME: cv.string,
            CONF_ICON: cv.icon,
            CONF_ALL: cv.boolean,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.match_all: vol.All(_conf_preprocess, GROUP_SCHEMA)})},
    extra=vol.ALLOW_EXTRA,
)


class GroupIntegrationRegistry:
    """Class to hold a registry of integrations."""

    on_off_mapping: dict[str, str] = {STATE_ON: STATE_OFF}
    off_on_mapping: dict[str, str] = {STATE_OFF: STATE_ON}
    on_states_by_domain: dict[str, set] = {}
    exclude_domains: set = set()

    def exclude_domain(self) -> None:
        """Exclude the current domain."""
        self.exclude_domains.add(current_domain.get())

    def on_off_states(self, on_states: set, off_state: str) -> None:
        """Register on and off states for the current domain."""
        for on_state in on_states:
            if on_state not in self.on_off_mapping:
                self.on_off_mapping[on_state] = off_state

        if len(on_states) == 1 and off_state not in self.off_on_mapping:
            self.off_on_mapping[off_state] = list(on_states)[0]

        self.on_states_by_domain[current_domain.get()] = set(on_states)


@bind_hass
def is_on(hass, entity_id):
    """Test if the group state is in its ON-state."""
    if REG_KEY not in hass.data:
        # Integration not setup yet, it cannot be on
        return False

    state = hass.states.get(entity_id)

    if state is not None:
        return state.state in hass.data[REG_KEY].on_off_mapping

    return False


@bind_hass
def expand_entity_ids(hass: HomeAssistant, entity_ids: Iterable[Any]) -> list[str]:
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    found_ids: list[str] = []
    for entity_id in entity_ids:
        if not isinstance(entity_id, str) or entity_id in (
            ENTITY_MATCH_NONE,
            ENTITY_MATCH_ALL,
        ):
            continue

        entity_id = entity_id.lower()

        try:
            # If entity_id points at a group, expand it
            domain, _ = ha.split_entity_id(entity_id)

            if domain == DOMAIN:
                child_entities = get_entity_ids(hass, entity_id)
                if entity_id in child_entities:
                    child_entities = list(child_entities)
                    child_entities.remove(entity_id)
                found_ids.extend(
                    ent_id
                    for ent_id in expand_entity_ids(hass, child_entities)
                    if ent_id not in found_ids
                )

            else:
                if entity_id not in found_ids:
                    found_ids.append(entity_id)

        except AttributeError:
            # Raised by split_entity_id if entity_id is not a string
            pass

    return found_ids


@bind_hass
def get_entity_ids(
    hass: HomeAssistant, entity_id: str, domain_filter: str | None = None
) -> list[str]:
    """Get members of this group.

    Async friendly.
    """
    group = hass.states.get(entity_id)

    if not group or ATTR_ENTITY_ID not in group.attributes:
        return []

    entity_ids = group.attributes[ATTR_ENTITY_ID]
    if not domain_filter:
        return cast(List[str], entity_ids)

    domain_filter = f"{domain_filter.lower()}."

    return [ent_id for ent_id in entity_ids if ent_id.startswith(domain_filter)]


@bind_hass
def groups_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get all groups that contain this entity.

    Async friendly.
    """
    if DOMAIN not in hass.data:
        return []

    groups = []

    for group in hass.data[DOMAIN].entities:
        if entity_id in group.tracking:
            groups.append(group.entity_id)

    return groups


async def async_setup(hass, config):
    """Set up all groups found defined in the configuration."""
    component = hass.data.get(DOMAIN)

    if component is None:
        component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)

    hass.data[REG_KEY] = GroupIntegrationRegistry()

    await async_process_integration_platforms(hass, DOMAIN, _process_group_platform)

    await _async_process_config(hass, config, component)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        # auto = list(filter(lambda e: not e.user_defined, component.entities))
        # fix for ais-dom groups defined in packages
        auto = list(component.entities)

        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await _async_process_config(hass, conf, component)

        await component.async_add_entities(auto)

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    service_lock = asyncio.Lock()

    async def locked_service_handler(service):
        """Handle a service with an async lock."""
        async with service_lock:
            await groups_service_handler(service)

    async def groups_service_handler(service):
        """Handle dynamic group service functions."""
        object_id = service.data[ATTR_OBJECT_ID]
        entity_id = f"{DOMAIN}.{object_id}"
        group = component.get_entity(entity_id)

        # new group
        if service.service == SERVICE_SET and group is None:
            entity_ids = (
                service.data.get(ATTR_ENTITIES)
                or service.data.get(ATTR_ADD_ENTITIES)
                or None
            )

            extra_arg = {
                attr: service.data[attr]
                for attr in (ATTR_ICON,)
                if service.data.get(attr) is not None
            }

            await Group.async_create_group(
                hass,
                service.data.get(ATTR_NAME, object_id),
                object_id=object_id,
                entity_ids=entity_ids,
                user_defined=False,
                mode=service.data.get(ATTR_ALL),
                **extra_arg,
            )
            return

        if group is None:
            _LOGGER.warning("%s:Group '%s' doesn't exist!", service.service, object_id)
            return

        # update group
        if service.service == SERVICE_SET:
            need_update = False

            if ATTR_ADD_ENTITIES in service.data:
                delta = service.data[ATTR_ADD_ENTITIES]
                entity_ids = set(group.tracking) | set(delta)
                await group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_ENTITIES in service.data:
                entity_ids = service.data[ATTR_ENTITIES]
                await group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_NAME in service.data:
                group.name = service.data[ATTR_NAME]
                need_update = True

            if ATTR_ICON in service.data:
                group.icon = service.data[ATTR_ICON]
                need_update = True

            if ATTR_ALL in service.data:
                group.mode = all if service.data[ATTR_ALL] else any
                need_update = True

            if need_update:
                group.async_write_ha_state()

            return

        # remove group
        if service.service == SERVICE_REMOVE:
            await component.async_remove_entity(entity_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET,
        locked_service_handler,
        schema=vol.All(
            vol.Schema(
                {
                    vol.Required(ATTR_OBJECT_ID): cv.slug,
                    vol.Optional(ATTR_NAME): cv.string,
                    vol.Optional(ATTR_ICON): cv.string,
                    vol.Optional(ATTR_ALL): cv.boolean,
                    vol.Exclusive(ATTR_ENTITIES, "entities"): cv.entity_ids,
                    vol.Exclusive(ATTR_ADD_ENTITIES, "entities"): cv.entity_ids,
                }
            )
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE,
        groups_service_handler,
        schema=vol.Schema({vol.Required(ATTR_OBJECT_ID): cv.slug}),
    )

    return True


async def _process_group_platform(hass, domain, platform):
    """Process a group platform."""
    current_domain.set(domain)
    platform.async_describe_on_off_states(hass, hass.data[REG_KEY])


async def _async_process_config(hass, config, component):
    """Process group configuration."""
    hass.data.setdefault(GROUP_ORDER, 0)

    tasks = []

    for object_id, conf in config.get(DOMAIN, {}).items():
        name = conf.get(CONF_NAME, object_id)
        entity_ids = conf.get(CONF_ENTITIES) or []
        icon = conf.get(CONF_ICON)
        mode = conf.get(CONF_ALL)

        # We keep track of the order when we are creating the tasks
        # in the same way that async_create_group does to make
        # sure we use the same ordering system.  This overcomes
        # the problem with concurrently creating the groups
        tasks.append(
            Group.async_create_group(
                hass,
                name,
                entity_ids,
                icon=icon,
                object_id=object_id,
                mode=mode,
                order=hass.data[GROUP_ORDER],
            )
        )

        # Keep track of the group order without iterating
        # every state in the state machine every time
        # we setup a new group
        hass.data[GROUP_ORDER] += 1

    await asyncio.gather(*tasks)


class GroupEntity(Entity):
    """Representation of a Group of entities."""

    @property
    def should_poll(self) -> bool:
        """Disable polling for group."""
        return False

    async def async_added_to_hass(self) -> None:
        """Register listeners."""

        async def _update_at_start(_):
            await self.async_update()
            self.async_write_ha_state()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _update_at_start)

    async def async_defer_or_update_ha_state(self) -> None:
        """Only update once at start."""
        if self.hass.state != CoreState.running:
            return

        await self.async_update()
        self.async_write_ha_state()

    @abstractmethod
    async def async_update(self) -> None:
        """Abstract method to update the entity."""


class Group(Entity):
    """Track a group of entity ids."""

    def __init__(
        self,
        hass,
        name,
        order=None,
        icon=None,
        user_defined=True,
        entity_ids=None,
        mode=None,
    ):
        """Initialize a group.

        This Object has factory function for creation.
        """
        self.hass = hass
        self._name = name
        self._state = None
        self._icon = icon
        self._set_tracked(entity_ids)
        self._on_off = None
        self._assumed = None
        self._on_states = None
        self.user_defined = user_defined
        self.mode = any
        if mode:
            self.mode = all
        self._order = order
        self._assumed_state = False
        self._async_unsub_state_changed = None

    @staticmethod
    def create_group(
        hass,
        name,
        entity_ids=None,
        user_defined=True,
        icon=None,
        object_id=None,
        mode=None,
        order=None,
    ):
        """Initialize a group."""
        return asyncio.run_coroutine_threadsafe(
            Group.async_create_group(
                hass, name, entity_ids, user_defined, icon, object_id, mode, order
            ),
            hass.loop,
        ).result()

    @staticmethod
    async def async_create_group(
        hass,
        name,
        entity_ids=None,
        user_defined=True,
        icon=None,
        object_id=None,
        mode=None,
        order=None,
    ):
        """Initialize a group.

        This method must be run in the event loop.
        """
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
            order=order,
            icon=icon,
            user_defined=user_defined,
            entity_ids=entity_ids,
            mode=mode,
        )

        group.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id or name, hass=hass
        )

        # If called before the platform async_setup is called (test cases)
        component = hass.data.get(DOMAIN)

        if component is None:
            component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)

        await component.async_add_entities([group])

        return group

    @property
    def should_poll(self):
        """No need to poll because groups will update themselves."""
        return False

    @property
    def name(self):
        """Return the name of the group."""
        return self._name

    @name.setter
    def name(self, value):
        """Set Group name."""
        self._name = value

    @property
    def state(self):
        """Return the state of the group."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the group."""
        return self._icon

    @icon.setter
    def icon(self, value):
        """Set Icon for group."""
        self._icon = value

    @property
    def extra_state_attributes(self):
        """Return the state attributes for the group."""
        data = {ATTR_ENTITY_ID: self.tracking, ATTR_ORDER: self._order}
        if not self.user_defined:
            data[ATTR_AUTO] = True

        return data

    @property
    def assumed_state(self):
        """Test if any member has an assumed state."""
        return self._assumed_state

    def update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs."""
        asyncio.run_coroutine_threadsafe(
            self.async_update_tracked_entity_ids(entity_ids), self.hass.loop
        ).result()

    async def async_update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs.

        This method must be run in the event loop.
        """
        self._async_stop()
        self._set_tracked(entity_ids)
        self._reset_tracked_state()
        self._async_start()

    def _set_tracked(self, entity_ids):
        """Tuple of entities to be tracked."""
        # tracking are the entities we want to track
        # trackable are the entities we actually watch

        if not entity_ids:
            self.tracking = ()
            self.trackable = ()
            return

        excluded_domains = self.hass.data[REG_KEY].exclude_domains

        tracking = []
        trackable = []
        for ent_id in entity_ids:
            ent_id_lower = ent_id.lower()
            domain = split_entity_id(ent_id_lower)[0]
            tracking.append(ent_id_lower)
            if domain not in excluded_domains:
                trackable.append(ent_id_lower)

        self.trackable = tuple(trackable)
        self.tracking = tuple(tracking)

    @callback
    def _async_start(self, *_):
        """Start tracking members and write state."""
        self._reset_tracked_state()
        self._async_start_tracking()
        self.async_write_ha_state()

    @callback
    def _async_start_tracking(self):
        """Start tracking members.

        This method must be run in the event loop.
        """
        if self.trackable and self._async_unsub_state_changed is None:
            self._async_unsub_state_changed = async_track_state_change_event(
                self.hass, self.trackable, self._async_state_changed_listener
            )

        self._async_update_group_state()

    @callback
    def _async_stop(self):
        """Unregister the group from Home Assistant.

        This method must be run in the event loop.
        """
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    async def async_update(self):
        """Query all members and determine current group state."""
        self._state = None
        self._async_update_group_state()

    async def async_added_to_hass(self):
        """Handle addition to Home Assistant."""
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, self._async_start
            )
            return

        if self.tracking:
            self._reset_tracked_state()
        self._async_start_tracking()

    async def async_will_remove_from_hass(self):
        """Handle removal from Home Assistant."""
        self._async_stop()

    async def _async_state_changed_listener(self, event):
        """Respond to a member state changing.

        This method must be run in the event loop.
        """
        # removed
        if self._async_unsub_state_changed is None:
            return

        self.async_set_context(event.context)
        new_state = event.data.get("new_state")

        if new_state is None:
            # The state was removed from the state machine
            self._reset_tracked_state()

        self._async_update_group_state(new_state)
        self.async_write_ha_state()

    def _reset_tracked_state(self):
        """Reset tracked state."""
        self._on_off = {}
        self._assumed = {}
        self._on_states = set()

        for entity_id in self.trackable:
            state = self.hass.states.get(entity_id)

            if state is not None:
                self._see_state(state)

    def _see_state(self, new_state):
        """Keep track of the the state."""
        entity_id = new_state.entity_id
        domain = new_state.domain
        state = new_state.state
        registry = self.hass.data[REG_KEY]
        self._assumed[entity_id] = new_state.attributes.get(ATTR_ASSUMED_STATE)

        if domain not in registry.on_states_by_domain:
            # Handle the group of a group case
            if state in registry.on_off_mapping:
                self._on_states.add(state)
            elif state in registry.off_on_mapping:
                self._on_states.add(registry.off_on_mapping[state])
            self._on_off[entity_id] = state in registry.on_off_mapping
        else:
            entity_on_state = registry.on_states_by_domain[domain]
            if domain in self.hass.data[REG_KEY].on_states_by_domain:
                self._on_states.update(entity_on_state)
            self._on_off[entity_id] = state in entity_on_state

    @callback
    def _async_update_group_state(self, tr_state=None):
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
            on_state = list(self._on_states)[0]
        # If we do not have an on state for any domains
        # we use None (which will be STATE_UNKNOWN)
        elif num_on_states == 0:
            self._state = None
            return
        # If the entity domains have more than one
        # on state, we use STATE_ON/STATE_OFF
        else:
            on_state = STATE_ON
        group_is_on = self.mode(self._on_off.values())
        if group_is_on:
            self._state = on_state
        else:
            self._state = self.hass.data[REG_KEY].on_off_mapping[on_state]
