"""Support for restoring entity states on startup."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import Any, Self, cast

from homeassistant.const import ATTR_RESTORED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, State, callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import json_loads

from . import start
from .entity import Entity
from .event import async_track_time_interval
from .frame import report
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


async def async_load(hass: HomeAssistant) -> None:
    """Load the restore state task."""
    await async_get(hass).async_setup()


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

    @classmethod
    async def async_get_instance(cls, hass: HomeAssistant) -> RestoreStateData:
        """Return the instance of this class."""
        # Nothing should actually be calling this anymore, but we'll keep it
        # around for a while to avoid breaking custom components.
        #
        # In fact they should not be accessing this at all.
        report(
            "restore_state.RestoreStateData.async_get_instance is deprecated, "
            "and not intended to be called by custom components; Please"
            "refactor your code to use RestoreEntity instead;"
            " restore_state.async_get(hass) can be used in the meantime",
        )
        return async_get(hass)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the restore state data class."""
        self.hass: HomeAssistant = hass
        self.store = Store[list[dict[str, Any]]](
            hass, STORAGE_VERSION, STORAGE_KEY, encoder=JSONEncoder
        )
        self.last_states: dict[str, StoredState] = {}
        self.entities: dict[str, RestoreEntity] = {}

    async def async_setup(self) -> None:
        """Set up up the instance of this data helper."""
        await self.async_load()

        @callback
        def hass_start(hass: HomeAssistant) -> None:
            """Start the restore state task."""
            self.async_setup_dump()

        start.async_at_start(self.hass, hass_start)

    async def async_load(self) -> None:
        """Load the instance of this data helper."""
        try:
            stored_states = await self.store.async_load()
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
        """
        now = dt_util.utcnow()
        all_states = self.hass.states.async_all()
        # Entities currently backed by an entity object
        current_states_by_entity_id = {
            state.entity_id: state
            for state in all_states
            if not state.attributes.get(ATTR_RESTORED)
        }

        # Start with the currently registered states
        stored_states = [
            StoredState(
                current_states_by_entity_id[entity_id],
                entity.extra_restore_state_data,
                now,
            )
            for entity_id, entity in self.entities.items()
            if entity_id in current_states_by_entity_id
        ]
        expiration_time = now - STATE_EXPIRATION

        for entity_id, stored_state in self.last_states.items():
            # Don't save old states that have entities in the current run
            # They are either registered and already part of stored_states,
            # or no longer care about restoring.
            if entity_id in current_states_by_entity_id:
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
            await self.store.async_save(
                [
                    stored_state.as_dict()
                    for stored_state in self.async_get_stored_states()
                ]
            )
        except HomeAssistantError as exc:
            _LOGGER.error("Error saving current states", exc_info=exc)

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
        self.entities[entity.entity_id] = entity

    @callback
    def async_restore_entity_removed(
        self, entity_id: str, extra_data: ExtraStoredData | None
    ) -> None:
        """Unregister this entity from saving state."""
        # When an entity is being removed from hass, store its last state. This
        # allows us to support state restoration if the entity is removed, then
        # re-added while hass is still running.
        state = self.hass.states.get(entity_id)
        # To fully mimic all the attribute data types when loaded from storage,
        # we're going to serialize it to JSON and then re-load it.
        if state is not None:
            state = State.from_dict(json_loads(state.as_dict_json))  # type: ignore[arg-type]
        if state is not None:
            self.last_states[entity_id] = StoredState(
                state, extra_data, dt_util.utcnow()
            )

        del self.entities[entity_id]


class RestoreEntity(Entity):
    """Mixin class for restoring previous entity state."""

    async def async_internal_added_to_hass(self) -> None:
        """Register this entity as a restorable entity."""
        await super().async_internal_added_to_hass()
        async_get(self.hass).async_restore_entity_added(self)

    async def async_internal_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        async_get(self.hass).async_restore_entity_removed(
            self.entity_id, self.extra_restore_state_data
        )
        await super().async_internal_will_remove_from_hass()

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
