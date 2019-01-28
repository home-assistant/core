"""Support for restoring entity states on startup."""
import asyncio
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, List, Set, Optional  # noqa  pylint_disable=unused-import

from homeassistant.core import (
    HomeAssistant, callback, State, CoreState, valid_entity_id)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store  # noqa  pylint_disable=unused-import

DATA_RESTORE_STATE_TASK = 'restore_state_task'

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = 'core.restore_state'
STORAGE_VERSION = 1

# How long between periodically saving the current states to disk
STATE_DUMP_INTERVAL = timedelta(minutes=15)

# How long should a saved state be preserved if the entity no longer exists
STATE_EXPIRATION = timedelta(days=7)


class StoredState:
    """Object to represent a stored state."""

    def __init__(self, state: State, last_seen: datetime) -> None:
        """Initialize a new stored state."""
        self.state = state
        self.last_seen = last_seen

    def as_dict(self) -> Dict:
        """Return a dict representation of the stored state."""
        return {
            'state': self.state.as_dict(),
            'last_seen': self.last_seen,
        }

    @classmethod
    def from_dict(cls, json_dict: Dict) -> 'StoredState':
        """Initialize a stored state from a dict."""
        last_seen = json_dict['last_seen']

        if isinstance(last_seen, str):
            last_seen = dt_util.parse_datetime(last_seen)

        return cls(State.from_dict(json_dict['state']), last_seen)


class RestoreStateData():
    """Helper class for managing the helper saved data."""

    @classmethod
    async def async_get_instance(
            cls, hass: HomeAssistant) -> 'RestoreStateData':
        """Get the singleton instance of this data helper."""
        task = hass.data.get(DATA_RESTORE_STATE_TASK)

        if task is None:
            async def load_instance(hass: HomeAssistant) -> 'RestoreStateData':
                """Set up the restore state helper."""
                data = cls(hass)

                try:
                    stored_states = await data.store.async_load()
                except HomeAssistantError as exc:
                    _LOGGER.error("Error loading last states", exc_info=exc)
                    stored_states = None

                if stored_states is None:
                    _LOGGER.debug('Not creating cache - no saved states found')
                    data.last_states = {}
                else:
                    data.last_states = {
                        item['state']['entity_id']: StoredState.from_dict(item)
                        for item in stored_states
                        if valid_entity_id(item['state']['entity_id'])}
                    _LOGGER.debug(
                        'Created cache with %s', list(data.last_states))

                if hass.state == CoreState.running:
                    data.async_setup_dump()
                else:
                    hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_START, data.async_setup_dump)

                return data

            task = hass.data[DATA_RESTORE_STATE_TASK] = hass.async_create_task(
                load_instance(hass))

        return await task

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the restore state data class."""
        self.hass = hass  # type: HomeAssistant
        self.store = Store(
            hass, STORAGE_VERSION, STORAGE_KEY,
            encoder=JSONEncoder)  # type: Store
        self.last_states = {}  # type: Dict[str, StoredState]
        self.entity_ids = set()  # type: Set[str]

    def async_get_stored_states(self) -> List[StoredState]:
        """Get the set of states which should be stored.

        This includes the states of all registered entities, as well as the
        stored states from the previous run, which have not been created as
        entities on this run, and have not expired.
        """
        now = dt_util.utcnow()
        all_states = self.hass.states.async_all()
        current_entity_ids = set(state.entity_id for state in all_states)

        # Start with the currently registered states
        stored_states = [StoredState(state, now) for state in all_states
                         if state.entity_id in self.entity_ids]

        expiration_time = now - STATE_EXPIRATION

        for entity_id, stored_state in self.last_states.items():
            # Don't save old states that have entities in the current run
            if entity_id in current_entity_ids:
                continue

            # Don't save old states that have expired
            if stored_state.last_seen < expiration_time:
                continue

            stored_states.append(stored_state)

        return stored_states

    async def async_dump_states(self) -> None:
        """Save the current state machine to storage."""
        _LOGGER.debug("Dumping states")
        try:
            await self.store.async_save([
                stored_state.as_dict()
                for stored_state in self.async_get_stored_states()])
        except HomeAssistantError as exc:
            _LOGGER.error("Error saving current states", exc_info=exc)

    @callback
    def async_setup_dump(self, *args: Any) -> None:
        """Set up the restore state listeners."""
        # Dump the initial states now. This helps minimize the risk of having
        # old states loaded by overwritting the last states once home assistant
        # has started and the old states have been read.
        self.hass.async_create_task(self.async_dump_states())

        # Dump states periodically
        async_track_time_interval(
            self.hass, lambda *_: self.hass.async_create_task(
                self.async_dump_states()), STATE_DUMP_INTERVAL)

        # Dump states when stopping hass
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda *_: self.hass.async_create_task(
                self.async_dump_states()))

    @callback
    def async_restore_entity_added(self, entity_id: str) -> None:
        """Store this entity's state when hass is shutdown."""
        self.entity_ids.add(entity_id)

    @callback
    def async_restore_entity_removed(self, entity_id: str) -> None:
        """Unregister this entity from saving state."""
        # When an entity is being removed from hass, store its last state. This
        # allows us to support state restoration if the entity is removed, then
        # re-added while hass is still running.
        self.last_states[entity_id] = StoredState(
            self.hass.states.get(entity_id), dt_util.utcnow())

        self.entity_ids.remove(entity_id)


class RestoreEntity(Entity):
    """Mixin class for restoring previous entity state."""

    async def async_added_to_hass(self) -> None:
        """Register this entity as a restorable entity."""
        _, data = await asyncio.gather(
            super().async_added_to_hass(),
            RestoreStateData.async_get_instance(self.hass),
        )
        data.async_restore_entity_added(self.entity_id)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        _, data = await asyncio.gather(
            super().async_will_remove_from_hass(),
            RestoreStateData.async_get_instance(self.hass),
        )
        data.async_restore_entity_removed(self.entity_id)

    async def async_get_last_state(self) -> Optional[State]:
        """Get the entity state from the previous run."""
        if self.hass is None or self.entity_id is None:
            # Return None if this entity isn't added to hass yet
            _LOGGER.warning("Cannot get last state. Entity not added to hass")
            return None
        data = await RestoreStateData.async_get_instance(self.hass)
        if self.entity_id not in data.last_states:
            return None
        return data.last_states[self.entity_id].state
