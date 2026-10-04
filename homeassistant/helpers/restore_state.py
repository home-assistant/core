"""Support for restoring entity states on startup."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import Any, Self, cast, override

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EntityStateAttribute
from homeassistant.core import Event, HomeAssistant, State, callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError, UnsupportedStorageVersionError
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import json_loads

from . import entity_registry as er, start
from .entity import Entity
from .event import async_track_time_interval
from .json import JSONEncoder
from .singleton import singleton
from .storage import Store

DATA_RESTORE_STATE: HassKey[RestoreStateData] = HassKey("restore_state")

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "core.restore_state"
STORAGE_VERSION = 1

# How long between periodically saving the current states to disk
STATE_DUMP_INTERVAL = timedelta(minutes=15)

# How long should a saved state be preserved if the entity no longer exists
STATE_EXPIRATION = timedelta(days=7)


class ExtraStoredData(ABC):
    """Object to hold extra stored data."""

    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data.

        Must be serializable by Home Assistant's JSONEncoder.
        """


class RestoredExtraData(ExtraStoredData):
    """Object to hold extra stored data loaded from storage."""

    def __init__(self, json_dict: dict[str, Any]) -> None:
        """Object to hold extra stored data."""
        self.json_dict = json_dict

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return self.json_dict


class StoredState:
    """Object to represent a stored state."""

    def __init__(
        self,
        state: State,
        extra_data: ExtraStoredData | None,
        last_seen: datetime,
    ) -> None:
        """Initialize a new stored state."""
        self.extra_data = extra_data
        self.last_seen = last_seen
        self.state = state

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored state to be JSON serialized."""
        return {
            "state": self.state.json_fragment,
            "extra_data": self.extra_data.as_dict() if self.extra_data else None,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, json_dict: dict) -> Self:
        """Initialize a stored state from a dict."""
        extra_data_dict = json_dict.get("extra_data")
        extra_data = RestoredExtraData(extra_data_dict) if extra_data_dict else None
        last_seen = json_dict["last_seen"]

        if isinstance(last_seen, str):
            last_seen = dt_util.parse_datetime(last_seen)

        return cls(
            cast(State, State.from_dict(json_dict["state"])), extra_data, last_seen
        )


async def async_load(hass: HomeAssistant, *, load_empty: bool = False) -> None:
    """Load the restore state task."""
    data = async_get(hass)
    if load_empty:
        data.set_load_empty()
    await data.async_setup()


@callback
@singleton(DATA_RESTORE_STATE)
def async_get(hass: HomeAssistant) -> RestoreStateData:
    """Get the restore state data helper."""
    return RestoreStateData(hass)


class RestoreStateData:
    """Helper class for managing the helper saved data."""

    @classmethod
    async def async_save_persistent_states(cls, hass: HomeAssistant) -> None:
        """Dump states now."""
        await async_get(hass).async_dump_states()

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the restore state data class."""
        self.hass: HomeAssistant = hass
        self.store = Store[list[dict[str, Any]]](
            hass, STORAGE_VERSION, STORAGE_KEY, encoder=JSONEncoder
        )
        self.last_states: dict[str, StoredState] = {}
        self.entities: dict[str, RestoreEntity] = {}
        # Entities which stored their state on removal but may still be in
        # the state machine until the removal completes
        self._removing: set[str] = set()

    def set_load_empty(self) -> None:
        """Set the store to load empty and become read-only."""
        self.store.set_load_empty()

    async def async_setup(self) -> None:
        """Set up up the instance of this data helper."""
        await self.async_load()

        @callback
        def hass_start(hass: HomeAssistant) -> None:
            """Start the restore state task."""
            self.async_setup_dump()

        start.async_at_start(self.hass, hass_start)

        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._async_entity_registry_updated,
            event_filter=_entity_id_changed_filter,
        )

    @callback
    def _async_entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Move the stored state of an entity which is not loaded."""
        data = event.data
        assert data["action"] == "update" and "old_entity_id" in data
        old_entity_id = data["old_entity_id"]
        # Loaded entities move their stored state when they are added again
        if old_entity_id in self.entities or self._is_removing(old_entity_id):
            return
        # A loaded entity may already have moved its stored state to the new id
        if old_entity_id not in self.last_states:
            return
        self.async_restore_entity_id_changed(old_entity_id, data["entity_id"])

    @callback
    def _is_removing(self, entity_id: str) -> bool:
        """Return if the entity is being removed and its state is still live."""
        return (
            entity_id in self._removing
            and (state := self.hass.states.get(entity_id)) is not None
            and not state.attributes.get(EntityStateAttribute.RESTORED)
        )

    async def async_load(self) -> None:
        """Load the instance of this data helper."""
        try:
            stored_states = await self.store.async_load()
        except UnsupportedStorageVersionError:
            raise
        except HomeAssistantError as exc:
            _LOGGER.error("Error loading last states", exc_info=exc)
            stored_states = None

        if stored_states is None:
            _LOGGER.debug("Not creating cache - no saved states found")
            self.last_states = {}
        else:
            self.last_states = {
                item["state"]["entity_id"]: StoredState.from_dict(item)
                for item in stored_states
                if valid_entity_id(item["state"]["entity_id"])
            }
            _LOGGER.debug("Created cache with %s", list(self.last_states))

    @callback
    def async_get_stored_states(self) -> list[StoredState]:
        """Get the set of states which should be stored.

        This includes the states of all registered entities, as well as the
        stored states from the previous run, which have not been created as
        entities on this run, and have not expired.

        Stored states that will not be saved are dropped from memory too.
        """
        now = dt_util.utcnow()
        all_states = self.hass.states.async_all()
        # Entities currently backed by an entity object
        current_states_by_entity_id = {
            state.entity_id: state
            for state in all_states
            if not state.attributes.get(EntityStateAttribute.RESTORED)
        }

        # Start with the currently registered states
        stored_states: list[StoredState] = []
        for entity_id, entity in self.entities.items():
            if entity_id not in current_states_by_entity_id:
                continue
            try:
                extra_data = entity.extra_restore_state_data
            except Exception:
                _LOGGER.exception(
                    "Error getting extra restore state data for %s", entity_id
                )
                continue
            stored_states.append(
                StoredState(
                    current_states_by_entity_id[entity_id],
                    extra_data,
                    now,
                )
            )
        expiration_time = now - STATE_EXPIRATION
        last_states: dict[str, StoredState] = {}

        for entity_id, stored_state in self.last_states.items():
            # Don't save old states that have entities in the current run
            # They are either registered and already part of stored_states,
            # or no longer care about restoring. Entities which are being
            # removed are no longer registered but need their stored state.
            if entity_id in current_states_by_entity_id:
                if entity_id not in self._removing:
                    continue
            else:
                self._removing.discard(entity_id)

            # Don't save old states that have expired
            if stored_state.last_seen < expiration_time:
                continue

            stored_states.append(stored_state)
            last_states[entity_id] = stored_state

        self.last_states = last_states

        return stored_states

    async def async_dump_states(self) -> None:
        """Save the current state machine to storage."""
        _LOGGER.debug("Dumping states")
        try:
            await self.store.async_save(
                [
                    stored_state.as_dict()
                    for stored_state in self.async_get_stored_states()
                ]
            )
        except HomeAssistantError as exc:
            _LOGGER.error("Error saving current states", exc_info=exc)
        except Exception:
            _LOGGER.exception("Unexpected error saving current states")

    @callback
    def async_setup_dump(self, *args: Any) -> None:
        """Set up the restore state listeners."""

        async def _async_dump_states(*_: Any) -> None:
            await self.async_dump_states()

        # Dump the initial states now. This helps minimize the risk of having
        # old states loaded by overwriting the last states once Home Assistant
        # has started and the old states have been read.
        self.hass.async_create_task_internal(
            _async_dump_states(), "RestoreStateData dump"
        )

        # Dump states periodically
        cancel_interval = async_track_time_interval(
            self.hass,
            _async_dump_states,
            STATE_DUMP_INTERVAL,
            name="RestoreStateData dump states",
        )

        async def _async_dump_states_at_stop(*_: Any) -> None:
            cancel_interval()
            await self.async_dump_states()

        # Dump states when stopping hass
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_dump_states_at_stop
        )

    @callback
    def async_restore_entity_added(self, entity: RestoreEntity) -> None:
        """Store this entity's state when hass is shutdown."""
        self._removing.discard(entity.entity_id)
        self.entities[entity.entity_id] = entity

    @callback
    def async_restore_entity_removed(
        self,
        entity_id: str,
        state: State | None,
        extra_data: ExtraStoredData | None,
    ) -> None:
        """Unregister this entity from saving state."""
        # When an entity is being removed from hass, store its last state. This
        # allows us to support state restoration if the entity is removed, then
        # re-added while hass is still running.
        # To fully mimic all the attribute data types when loaded from storage,
        # we're going to serialize it to JSON and then re-load it.
        if state is not None:
            state = State.from_dict(json_loads(state.as_dict_json))  # type: ignore[arg-type]
        if state is not None:
            self.last_states[entity_id] = StoredState(
                state, extra_data, dt_util.utcnow()
            )
            self._removing.add(entity_id)

        del self.entities[entity_id]

    @callback
    def async_restore_entity_id_changed(
        self, old_entity_id: str, new_entity_id: str
    ) -> None:
        """Move the stored state of an entity whose entity_id has changed."""
        self._removing.discard(old_entity_id)
        if (stored_state := self.last_states.pop(old_entity_id, None)) is None:
            # Never restore another entity's leftover state under the new id
            self.last_states.pop(new_entity_id, None)
            return
        state = stored_state.state
        # The store is keyed by State.entity_id when loaded
        stored_state.state = State(
            new_entity_id,
            state.state,
            state.attributes,
            last_changed=state.last_changed,
            last_reported=state.last_reported,
            last_updated=state.last_updated,
            context=state.context,
            validate_entity_id=False,
        )
        self.last_states[new_entity_id] = stored_state


@callback
def _entity_id_changed_filter(event_data: er.EventEntityRegistryUpdatedData) -> bool:
    """Filter entity registry updates changing the entity_id."""
    return event_data["action"] == "update" and "old_entity_id" in event_data


class RestoreEntity(Entity):
    """Mixin class for restoring previous entity state."""

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Register this entity as a restorable entity."""
        await super().async_internal_added_to_hass()
        async_get(self.hass).async_restore_entity_added(self)

    @override
    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            extra_data = self.extra_restore_state_data
        except Exception:
            _LOGGER.exception(
                "Error getting extra restore state data for %s", self.entity_id
            )
            state = None
            extra_data = None
        else:
            state = self.hass.states.get(self.entity_id)
        data = async_get(self.hass)
        data.async_restore_entity_removed(self.entity_id, state, extra_data)
        # An entity disabled while changing entity_id is not added again under
        # the new entity_id, so the entity_id change hook does not run
        if (
            (registry_entry := self.registry_entry) is not None
            and registry_entry.disabled
            and registry_entry.entity_id != self.entity_id
        ):
            data.async_restore_entity_id_changed(
                self.entity_id, registry_entry.entity_id
            )
        await super().async_internal_will_remove_from_hass()

    @callback
    @override
    def async_internal_entity_id_changed(self, old_entity_id: str) -> None:
        """Move the stored state to the new entity_id."""
        super().async_internal_entity_id_changed(old_entity_id)
        async_get(self.hass).async_restore_entity_id_changed(
            old_entity_id, self.entity_id
        )

    @callback
    def _async_get_restored_data(self) -> StoredState | None:
        """Get data stored for an entity, if any."""
        if self.hass is None or self.entity_id is None:
            # Return None if this entity isn't added to hass yet
            _LOGGER.warning(  # type: ignore[unreachable]
                "Cannot get last state. Entity not added to hass"
            )
            return None
        return async_get(self.hass).last_states.get(self.entity_id)

    async def async_get_last_state(self) -> State | None:
        """Get the entity state from the previous run."""
        if (stored_state := self._async_get_restored_data()) is None:
            return None
        return stored_state.state

    async def async_get_last_extra_data(self) -> ExtraStoredData | None:
        """Get the entity specific state data from the previous run."""
        if (stored_state := self._async_get_restored_data()) is None:
            return None
        return stored_state.extra_data

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        """Return entity specific state data to be restored.

        Implemented by platform classes.
        """
        return None
