"""The tests for the Restore component."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
import logging
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_get_platform_without_config_entry
from homeassistant.helpers.restore_state import (
    DATA_RESTORE_STATE,
    STORAGE_KEY,
    ExtraStoredData,
    RestoreEntity,
    RestoreStateData,
    StoredState,
    async_get,
    async_load,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from tests.common import (
    MockEntityPlatform,
    MockModule,
    MockPlatform,
    async_fire_time_changed,
    json_round_trip,
    mock_integration,
    mock_platform,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"
PLATFORM = "test_platform"


async def test_caching_data(hass: HomeAssistant) -> None:
    """Test that we cache data."""
    now = dt_util.utcnow()
    stored_states = [
        StoredState(State("input_boolean.b0", "on"), None, now),
        StoredState(State("input_boolean.b1", "on"), None, now),
        StoredState(State("input_boolean.b2", "on"), None, now),
    ]

    data = async_get(hass)
    await hass.async_block_till_done()
    await data.store.async_save([state.as_dict() for state in stored_states])

    # Emulate a fresh load
    hass.data.pop(DATA_RESTORE_STATE)

    with (
        patch(
            "homeassistant.helpers.restore_state.Store.async_load",
            side_effect=HomeAssistantError,
        ),
        patch("homeassistant.helpers.restore_state.Store.async_save"),
    ):
        # Failure to load should not be treated as fatal
        await async_load(hass)

    data = async_get(hass)
    assert data.last_states == {}

    # Mock that only b1 is present this run
    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        await async_load(hass)
        await hass.async_block_till_done()

    data = async_get(hass)

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b1"

    # Mock that only b1 is present this run
    state = await entity.async_get_last_state()

    assert state is not None
    assert state.entity_id == "input_boolean.b1"
    assert state.state == "on"

    assert mock_write_data.called


async def test_periodic_write(hass: HomeAssistant) -> None:
    """Test that we write periodiclly but not after stop."""
    data = async_get(hass)
    await hass.async_block_till_done()
    await data.store.async_save([])

    # Emulate a fresh load
    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        hass.data.pop(DATA_RESTORE_STATE)
        await async_load(hass)
        data = async_get(hass)

        entity = RestoreEntity()
        entity.hass = hass
        entity.entity_id = "input_boolean.b1"

        await entity.async_get_last_state()
        await hass.async_block_till_done()

    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=15))
        await hass.async_block_till_done()

    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=30))
        await hass.async_block_till_done()

    assert not mock_write_data.called


async def test_save_persistent_states(hass: HomeAssistant) -> None:
    """Test we cancel the running job, save data, and verify periodic job continues."""
    data = async_get(hass)
    await hass.async_block_till_done()
    await data.store.async_save([])

    # Emulate a fresh load
    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        hass.data.pop(DATA_RESTORE_STATE)
        await async_load(hass)
        data = async_get(hass)

        entity = RestoreEntity()
        entity.hass = hass
        entity.entity_id = "input_boolean.b1"

        await entity.async_get_last_state()
        await hass.async_block_till_done()

    # Startup Save
    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()

    # Not quite the first interval
    assert not mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        await RestoreStateData.async_save_persistent_states(hass)
        await hass.async_block_till_done()

    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
        await hass.async_block_till_done()
    # Verify still saving
    assert mock_write_data.called

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    # Verify normal shutdown
    assert mock_write_data.called


async def test_hass_starting(hass: HomeAssistant) -> None:
    """Test that we cache data."""
    hass.set_state(CoreState.starting)

    now = dt_util.utcnow()
    stored_states = [
        StoredState(State("input_boolean.b0", "on"), None, now),
        StoredState(State("input_boolean.b1", "on"), None, now),
        StoredState(State("input_boolean.b2", "on"), None, now),
    ]

    data = async_get(hass)
    await hass.async_block_till_done()
    await data.store.async_save([state.as_dict() for state in stored_states])

    # Emulate a fresh load
    hass.set_state(CoreState.not_running)
    hass.data.pop(DATA_RESTORE_STATE)
    await async_load(hass)
    data = async_get(hass)

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b1"

    all_states = hass.states.async_all()
    assert len(all_states) == 0
    hass.states.async_set("input_boolean.b1", "on")

    # Mock that only b1 is present this run
    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        state = await entity.async_get_last_state()
        await hass.async_block_till_done()

    assert state is not None
    assert state.entity_id == "input_boolean.b1"
    assert state.state == "on"
    hass.states.async_remove("input_boolean.b1")

    # Assert that no data was written yet, since hass is still starting.
    assert not mock_write_data.called

    # Finish hass startup
    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    # Assert that this session states were written
    assert mock_write_data.called


async def test_dump_data(hass: HomeAssistant) -> None:
    """Test that we cache data."""
    states = [
        State("input_boolean.b0", "on"),
        State("input_boolean.b1", "on"),
        State("input_boolean.b2", "on"),
        State("input_boolean.b5", "unavailable", {"restored": True}),
    ]

    platform = MockEntityPlatform(hass, domain="input_boolean")
    entity = Entity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b0"
    await platform.async_add_entities([entity])

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b1"
    await platform.async_add_entities([entity])

    data = async_get(hass)
    now = dt_util.utcnow()
    data.last_states = {
        "input_boolean.b0": StoredState(State("input_boolean.b0", "off"), None, now),
        "input_boolean.b1": StoredState(State("input_boolean.b1", "off"), None, now),
        "input_boolean.b2": StoredState(State("input_boolean.b2", "off"), None, now),
        "input_boolean.b3": StoredState(State("input_boolean.b3", "off"), None, now),
        "input_boolean.b4": StoredState(
            State("input_boolean.b4", "off"),
            None,
            datetime(1985, 10, 26, 1, 22, tzinfo=dt_util.UTC),
        ),
        "input_boolean.b5": StoredState(State("input_boolean.b5", "off"), None, now),
    }

    for state in states:
        hass.states.async_set(state.entity_id, state.state, state.attributes)

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]

    for state in states:
        hass.states.async_remove(state.entity_id)
    # b0 should not be written, since it didn't extend RestoreEntity
    # b1 should be written, since it is present in the current run
    # b2 should not be written, since it is not registered with the helper
    # b3 should be written, since it is still not expired
    # b4 should not be written, since it is now expired
    # b5 should be written, since current state is restored by entity registry
    assert len(written_states) == 3
    state0 = json_round_trip(written_states[0])
    state1 = json_round_trip(written_states[1])
    state2 = json_round_trip(written_states[2])
    assert state0["state"]["entity_id"] == "input_boolean.b1"
    assert state0["state"]["state"] == "on"
    assert state1["state"]["entity_id"] == "input_boolean.b3"
    assert state1["state"]["state"] == "off"
    assert state2["state"]["entity_id"] == "input_boolean.b5"
    assert state2["state"]["state"] == "off"
    # States that are not written anymore are dropped from memory as well
    assert list(data.last_states) == ["input_boolean.b3", "input_boolean.b5"]

    # Test that removed entities are not persisted
    await entity.async_remove()

    for state in states:
        hass.states.async_set(state.entity_id, state.state, state.attributes)

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        await data.async_dump_states()

    assert mock_write_data.called
    args = mock_write_data.mock_calls[0][1]
    written_states = args[0]
    assert len(written_states) == 2
    state0 = json_round_trip(written_states[0])
    state1 = json_round_trip(written_states[1])
    assert state0["state"]["entity_id"] == "input_boolean.b3"
    assert state0["state"]["state"] == "off"
    assert state1["state"]["entity_id"] == "input_boolean.b5"
    assert state1["state"]["state"] == "off"


@pytest.mark.parametrize(
    "exception",
    [HomeAssistantError, RuntimeError],
)
async def test_dump_error(hass: HomeAssistant, exception: type[Exception]) -> None:
    """Test that errors during save are caught."""
    states = [
        State("input_boolean.b0", "on"),
        State("input_boolean.b1", "on"),
        State("input_boolean.b2", "on"),
    ]

    platform = MockEntityPlatform(hass, domain="input_boolean")
    entity = Entity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b0"
    await platform.async_add_entities([entity])

    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b1"
    await platform.async_add_entities([entity])

    data = async_get(hass)

    for state in states:
        hass.states.async_set(state.entity_id, state.state, state.attributes)

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save",
        side_effect=exception,
    ) as mock_write_data:
        await data.async_dump_states()

    assert mock_write_data.called


async def test_load_error(hass: HomeAssistant) -> None:
    """Test that we cache data."""
    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b1"

    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        side_effect=HomeAssistantError,
    ):
        state = await entity.async_get_last_state()

    assert state is None


async def test_state_saved_on_remove(hass: HomeAssistant) -> None:
    """Test that we save entity state on removal."""
    platform = MockEntityPlatform(hass, domain="input_boolean")
    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.b0"
    await platform.async_add_entities([entity])

    now = dt_util.utcnow()
    hass.states.async_set(
        "input_boolean.b0", "on", {"complicated": {"value": {1, 2, now}}}
    )

    data = async_get(hass)

    # No last states should currently be saved
    assert not data.last_states

    await entity.async_remove()

    # We should store the input boolean state when it is removed
    state = data.last_states["input_boolean.b0"].state
    assert state.state == "on"
    assert isinstance(state.attributes["complicated"]["value"], list)
    assert set(state.attributes["complicated"]["value"]) == {1, 2, now.isoformat()}


async def test_restoring_invalid_entity_id(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test restoring invalid entity IDs."""
    entity = RestoreEntity()
    entity.hass = hass
    entity.entity_id = "test.invalid__entity_id"
    now = dt_util.utcnow().isoformat()
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": [
            {
                "state": {
                    "entity_id": "test.invalid__entity_id",
                    "state": "off",
                    "attributes": {},
                    "last_changed": now,
                    "last_updated": now,
                    "context": {
                        "id": "3c2243ff5f30447eb12e7348cfd5b8ff",
                        "user_id": None,
                    },
                },
                "last_seen": dt_util.utcnow().isoformat(),
            }
        ],
    }

    state = await entity.async_get_last_state()
    assert state is None


async def test_restore_entity_end_to_end(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test restoring an entity end-to-end."""
    component_setup = Mock(return_value=True)

    setup_called = []

    entity_id = "test_domain.unnamed_device"
    data = async_get(hass)
    now = dt_util.utcnow()
    data.last_states = {
        entity_id: StoredState(State(entity_id, "stored"), None, now),
    }

    class MockRestoreEntity(RestoreEntity):
        """Mock restore entity."""

        def __init__(self) -> None:
            """Initialize the mock entity."""
            self._state: str | None = None

        @property
        def state(self) -> str | None:
            """Return the state."""
            return self._state

        async def async_added_to_hass(self) -> Coroutine[Any, Any, None]:
            """Run when entity about to be added to hass."""
            await super().async_added_to_hass()
            self._state = (await self.async_get_last_state()).state

    async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up the test platform."""
        async_add_entities([MockRestoreEntity()])
        setup_called.append(True)

    mock_integration(hass, MockModule(DOMAIN, setup=component_setup))
    mock_integration(hass, MockModule(PLATFORM, dependencies=[DOMAIN]))

    platform = MockPlatform(async_setup_platform=async_setup_platform)
    mock_platform(hass, f"{PLATFORM}.{DOMAIN}", platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    await component.async_setup({DOMAIN: {"platform": PLATFORM, "sensors": None}})
    await hass.async_block_till_done()
    assert component_setup.called

    assert f"{PLATFORM}.{DOMAIN}" in hass.config.components
    assert len(setup_called) == 1

    platform = async_get_platform_without_config_entry(hass, PLATFORM, DOMAIN)
    assert platform.platform_name == PLATFORM
    assert platform.domain == DOMAIN
    assert hass.states.get(entity_id).state == "stored"

    await data.async_dump_states()
    await hass.async_block_till_done()

    storage_data = hass_storage[STORAGE_KEY]["data"]
    assert len(storage_data) == 1
    assert storage_data[0]["state"]["entity_id"] == entity_id
    assert storage_data[0]["state"]["state"] == "stored"

    await platform.async_reset()

    assert hass.states.get(entity_id) is None

    # Make sure the entity still gets saved to restore state
    # even though the platform has been reset since it should
    # not be expired yet.
    await data.async_dump_states()
    await hass.async_block_till_done()

    storage_data = hass_storage[STORAGE_KEY]["data"]
    assert len(storage_data) == 1
    assert storage_data[0]["state"]["entity_id"] == entity_id
    assert storage_data[0]["state"]["state"] == "stored"


async def test_dump_states_with_failing_extra_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failing extra_restore_state_data skips only that entity."""

    class BadRestoreEntity(RestoreEntity):
        """Entity that raises on extra_restore_state_data."""

        @property
        def extra_restore_state_data(self) -> ExtraStoredData | None:
            raise RuntimeError("Unexpected error")

    states = [
        State("input_boolean.good", "on"),
        State("input_boolean.bad", "on"),
    ]

    platform = MockEntityPlatform(hass, domain="input_boolean")

    good_entity = RestoreEntity()
    good_entity.hass = hass
    good_entity.entity_id = "input_boolean.good"
    await platform.async_add_entities([good_entity])

    bad_entity = BadRestoreEntity()
    bad_entity.hass = hass
    bad_entity.entity_id = "input_boolean.bad"
    await platform.async_add_entities([bad_entity])

    for state in states:
        hass.states.async_set(state.entity_id, state.state, state.attributes)

    data = async_get(hass)

    with patch(
        "homeassistant.helpers.restore_state.Store.async_save"
    ) as mock_write_data:
        await data.async_dump_states()

    assert mock_write_data.called
    written_states = mock_write_data.mock_calls[0][1][0]

    # Only the good entity should be saved
    assert len(written_states) == 1
    state0 = json_round_trip(written_states[0])
    assert state0["state"]["entity_id"] == "input_boolean.good"
    assert state0["state"]["state"] == "on"

    assert "Error getting extra restore state data for input_boolean.bad" in caplog.text


async def test_entity_removal_with_failing_extra_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that entity removal succeeds even if extra_restore_state_data raises."""

    class BadRestoreEntity(RestoreEntity):
        """Entity that raises on extra_restore_state_data."""

        @property
        def extra_restore_state_data(self) -> ExtraStoredData | None:
            raise RuntimeError("Unexpected error")

    platform = MockEntityPlatform(hass, domain="input_boolean")
    entity = BadRestoreEntity()
    entity.hass = hass
    entity.entity_id = "input_boolean.bad"
    await platform.async_add_entities([entity])

    hass.states.async_set("input_boolean.bad", "on")

    data = async_get(hass)
    assert "input_boolean.bad" in data.entities

    await entity.async_remove()

    # Entity should be unregistered
    assert "input_boolean.bad" not in data.entities
    # No last state should be saved since extra data failed
    assert "input_boolean.bad" not in data.last_states

    assert "Error getting extra restore state data for input_boolean.bad" in caplog.text


class _CounterExtraData(ExtraStoredData):
    """Extra stored data holding a counter."""

    def __init__(self, count: int) -> None:
        """Initialize the extra data."""
        self.count = count

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {"count": self.count}


class _RenameRestoreEntity(RestoreEntity):
    """Restore entity recording what it restored each time it was added."""

    _attr_should_poll = False
    _attr_unique_id = "5678"

    def __init__(self) -> None:
        """Initialize the entity."""
        self._attr_state = "initial"
        self.count = 0
        self.restored: list[tuple[str, str | None, dict[str, Any] | None]] = []

    async def async_added_to_hass(self) -> None:
        """Restore the state and the counter."""
        last_state = await self.async_get_last_state()
        last_extra_data = await self.async_get_last_extra_data()
        self.restored.append(
            (
                self.entity_id,
                last_state.state if last_state else None,
                last_extra_data.as_dict() if last_extra_data else None,
            )
        )
        if last_state:
            self._attr_state = last_state.state
        if last_extra_data:
            self.count = last_extra_data.as_dict()["count"]

    async def async_will_remove_from_hass(self) -> None:
        """Suspend during removal."""
        # The stored state must be moved only after removal has completed
        await asyncio.sleep(0)

    @property
    def extra_restore_state_data(self) -> _CounterExtraData:
        """Return the counter."""
        return _CounterExtraData(self.count)

    def set_state(self, state: str, count: int) -> None:
        """Set the state and the counter."""
        self._attr_state = state
        self.count = count
        self.async_write_ha_state()


class _FailingRenameRestoreEntity(_RenameRestoreEntity):
    """Restore entity whose extra_restore_state_data raises."""

    @property
    def extra_restore_state_data(self) -> _CounterExtraData:
        """Raise."""
        raise RuntimeError("Unexpected error")


class _BlockingRenameRestoreEntity(_RenameRestoreEntity):
    """Restore entity which blocks during removal until released."""

    def __init__(self) -> None:
        """Initialize the entity."""
        super().__init__()
        self.removing = asyncio.Event()
        self.release = asyncio.Event()

    async def async_will_remove_from_hass(self) -> None:
        """Block until released."""
        self.removing.set()
        await self.release.wait()
        await super().async_will_remove_from_hass()


class _NoUniqueIdRestoreEntity(_RenameRestoreEntity):
    """Restore entity without a unique_id, which has no registry entry."""

    _attr_unique_id = None

    def __init__(self) -> None:
        """Initialize the entity."""
        super().__init__()
        self.entity_id = "test.test"


async def _async_add_rename_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity: _RenameRestoreEntity,
) -> MockEntityPlatform:
    """Register the entity as test.test and add it."""
    entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test"
    )
    platform = MockEntityPlatform(hass, domain="test")
    await platform.async_add_entities([entity])
    return platform


async def _async_add_no_registry_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity: _RenameRestoreEntity,
) -> MockEntityPlatform:
    """Add the entity without a registry entry."""
    platform = MockEntityPlatform(hass, domain="test")
    await platform.async_add_entities([entity])
    return platform


async def test_restore_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the state is restored after the entity_id is changed."""
    entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id
    entity.set_state("live", 3)

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await hass.async_block_till_done()

    assert entity.restored == [
        ("test.test", None, None),
        ("test.test2", "live", {"count": 3}),
    ]
    assert hass.states.get("test.test") is None
    assert hass.states.get("test.test2").state == "live"

    data = async_get(hass)
    assert list(data.entities) == ["test.test2"]
    assert not data.last_states
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]
    stored_state = data.last_states_by_entity_registry_id[entity_registry_id]
    assert stored_state.state.entity_id == "test.test2"

    entity.set_state("later", 4)
    await entity.async_remove()
    await data.async_dump_states()

    stored = hass_storage[STORAGE_KEY]["data"]
    assert [item["state"]["entity_id"] for item in stored] == ["test.test2"]
    assert stored[0]["entity_registry_id"] == entity_registry_id
    assert stored[0]["state"]["state"] == "later"
    assert stored[0]["extra_data"] == {"count": 4}


async def test_entity_id_change_while_not_loaded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the state is restored after the entity_id is changed while unloaded."""
    entity = _RenameRestoreEntity()
    platform = await _async_add_rename_entity(hass, entity_registry, entity)
    entity.set_state("live", 3)
    await entity.async_remove()
    data = async_get(hass)
    await data.async_dump_states()

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await hass.async_block_till_done()

    # The stored state survives a restart
    reloaded = RestoreStateData(hass)
    await reloaded.async_load()
    hass.data[DATA_RESTORE_STATE] = reloaded
    new_entity = _RenameRestoreEntity()
    await platform.async_add_entities([new_entity])

    assert new_entity.restored == [("test.test2", "live", {"count": 3})]


@pytest.mark.parametrize(
    ("entity_class", "expected_restored"),
    [
        pytest.param(
            _RenameRestoreEntity,
            ("test.test2", "live", {"count": 3}),
            id="own_state",
        ),
        pytest.param(
            _FailingRenameRestoreEntity,
            ("test.test2", None, None),
            id="failing_extra_data",
        ),
    ],
)
async def test_entity_id_change_and_disable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_class: type[_RenameRestoreEntity],
    expected_restored: tuple[str, str | None, dict[str, Any] | None],
) -> None:
    """Test changing the entity_id and disabling a loaded entity at once."""
    data = async_get(hass)
    data.last_states["test.test2"] = StoredState(
        State("test.test2", "foreign"), _CounterExtraData(99), dt_util.utcnow()
    )
    entity = entity_class()
    platform = await _async_add_rename_entity(hass, entity_registry, entity)
    entity.set_state("live", 3)

    entity_registry.async_update_entity(
        "test.test",
        new_entity_id="test.test2",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()
    assert hass.states.get("test.test") is None
    assert "test.test" not in data.last_states

    entity_registry.async_update_entity("test.test2", disabled_by=None)
    new_entity = _RenameRestoreEntity()
    await platform.async_add_entities([new_entity])
    assert new_entity.restored == [expected_restored]


@pytest.mark.parametrize(
    ("entity_class", "expected_restored"),
    [
        pytest.param(
            _RenameRestoreEntity,
            ("test.test2", "live", {"count": 3}),
            id="own_state",
        ),
        pytest.param(
            _FailingRenameRestoreEntity,
            ("test.test2", None, None),
            id="failing_extra_data",
        ),
    ],
)
async def test_entity_id_change_ignores_leftover_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_class: type[_RenameRestoreEntity],
    expected_restored: tuple[str, str | None, dict[str, Any] | None],
) -> None:
    """Test a leftover state stored under the new entity_id is not restored."""
    data = async_get(hass)
    data.last_states["test.test2"] = StoredState(
        State("test.test2", "foreign"), _CounterExtraData(99), dt_util.utcnow()
    )
    entity = entity_class()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity.set_state("live", 3)

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await hass.async_block_till_done()

    assert entity.restored == [("test.test", None, None), expected_restored]
    assert "test.test" not in data.last_states


async def test_entity_id_change_and_back(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing the entity_id back restores the latest state."""
    entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id
    entity.set_state("first", 1)

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await hass.async_block_till_done()
    entity.set_state("second", 2)

    entity_registry.async_update_entity("test.test2", new_entity_id="test.test")
    await hass.async_block_till_done()

    assert entity.restored == [
        ("test.test", None, None),
        ("test.test2", "first", {"count": 1}),
        ("test.test", "second", {"count": 2}),
    ]
    data = async_get(hass)
    assert not data.last_states
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]

    # A new entity taking the previous entity_id restores nothing
    other = RestoreEntity()
    other.hass = hass
    other.entity_id = "test.test2"
    assert await other.async_get_last_state() is None


async def test_restore_after_registry_entry_recreated(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the state is restored when a removed registry entry is recreated."""
    entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id
    entity.set_state("live", 3)

    entity_registry.async_remove("test.test")
    await hass.async_block_till_done()
    assert hass.states.get("test.test") is None
    data = async_get(hass)
    assert not data.last_states
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]
    # A state stored by entity_id meanwhile does not replace the entry's own
    data.last_states["test.test"] = StoredState(
        State("test.test", "foreign"), _CounterExtraData(99), dt_util.utcnow()
    )

    new_entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, new_entity)

    assert entity_registry.async_get("test.test").id == entity_registry_id
    assert new_entity.restored == [("test.test", "live", {"count": 3})]


async def test_dump_during_entity_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test a dump while the entity is being removed keeps its stored state."""
    entity = _BlockingRenameRestoreEntity()
    platform = await _async_add_rename_entity(hass, entity_registry, entity)
    entity.set_state("live", 3)
    data = async_get(hass)

    remove_task = hass.async_create_task(entity.async_remove(force_remove=True))
    await entity.removing.wait()
    assert hass.states.get("test.test").state == "live"
    await data.async_dump_states()
    stored = hass_storage[STORAGE_KEY]["data"]
    assert [item["state"]["entity_id"] for item in stored] == ["test.test"]
    assert stored[0]["state"]["state"] == "live"
    entity.release.set()
    await remove_task
    assert hass.states.get("test.test") is None

    # Once removed, the stored state is kept by later dumps
    await data.async_dump_states()
    assert len(data.last_states_by_entity_registry_id) == 1

    new_entity = _RenameRestoreEntity()
    await platform.async_add_entities([new_entity])
    assert new_entity.restored == [("test.test", "live", {"count": 3})]


async def test_dump_during_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test a dump while the entity is being renamed keeps its stored state."""
    entity = _BlockingRenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id
    data = async_get(hass)
    entity.set_state("live", 3)

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await entity.removing.wait()
    assert hass.states.get("test.test").state == "live"
    await data.async_dump_states()
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]
    entity.release.set()
    await hass.async_block_till_done()

    assert entity.restored == [
        ("test.test", None, None),
        ("test.test2", "live", {"count": 3}),
    ]
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]


@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="not_loaded"),
        pytest.param(er.RegistryEntryDisabler.USER, id="disabled"),
    ],
)
async def test_entity_id_change_not_loaded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test changing the entity_id of an entity which is not loaded."""
    data = async_get(hass)
    registry_entry = entity_registry.async_get_or_create(
        "test",
        "test_platform",
        "5678",
        suggested_object_id="test",
        disabled_by=disabled_by,
    )
    data.last_states_by_entity_registry_id[registry_entry.id] = StoredState(
        State("test.test", "stored"),
        _CounterExtraData(3),
        dt_util.utcnow(),
        registry_entry.id,
    )
    data.last_states["test.test2"] = StoredState(
        State("test.test2", "foreign"), _CounterExtraData(99), dt_util.utcnow()
    )

    entity_registry.async_update_entity(
        "test.test", new_entity_id="test.test2", disabled_by=None
    )
    await hass.async_block_till_done()
    entity = _RenameRestoreEntity()
    platform = MockEntityPlatform(hass, domain="test")
    await platform.async_add_entities([entity])

    assert entity.restored == [("test.test2", "stored", {"count": 3})]


async def test_entity_id_change_after_unload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing the entity_id of an entity removed without a dump since."""
    entity = _RenameRestoreEntity()
    platform = await _async_add_rename_entity(hass, entity_registry, entity)
    entity.set_state("live", 3)
    await entity.async_remove()
    assert hass.states.get("test.test").state == "unavailable"

    entity_registry.async_update_entity("test.test", new_entity_id="test.test2")
    await hass.async_block_till_done()

    new_entity = _RenameRestoreEntity()
    await platform.async_add_entities([new_entity])
    assert new_entity.restored == [("test.test2", "live", {"count": 3})]


async def test_restore_after_unique_id_added(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test an entity which gets a unique_id restores the state stored by entity_id."""
    platform = MockEntityPlatform(hass, domain="test")
    no_registry_entity = _NoUniqueIdRestoreEntity()
    await platform.async_add_entities([no_registry_entity])
    assert entity_registry.async_get("test.test") is None
    no_registry_entity.set_state("live", 3)
    await no_registry_entity.async_remove()
    data = async_get(hass)
    await data.async_dump_states()
    stored = hass_storage[STORAGE_KEY]["data"]
    assert [item["entity_registry_id"] for item in stored] == [None]

    await data.async_load()
    entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id

    assert entity.restored == [("test.test", "live", {"count": 3})]
    assert not data.last_states
    assert list(data.last_states_by_entity_registry_id) == [entity_registry_id]


async def test_state_stored_with_registry_entry_not_restored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test an entity without a registry entry ignores a state stored by entry."""
    entity = _RenameRestoreEntity()
    platform = await _async_add_rename_entity(hass, entity_registry, entity)
    entity_registry_id = entity_registry.async_get("test.test").id
    entity.set_state("foreign", 99)
    await entity.async_remove(force_remove=True)
    entity_registry.async_remove("test.test")
    data = async_get(hass)
    await data.async_dump_states()
    stored = hass_storage[STORAGE_KEY]["data"]
    assert [item["entity_registry_id"] for item in stored] == [entity_registry_id]
    assert [item["state"]["entity_id"] for item in stored] == ["test.test"]

    await data.async_load()
    no_registry_entity = _NoUniqueIdRestoreEntity()
    await platform.async_add_entities([no_registry_entity])

    assert entity_registry.async_get("test.test") is None
    assert no_registry_entity.restored == [("test.test", None, None)]


def _register_test_entity(entity_registry: er.EntityRegistry) -> None:
    """Register test.test."""
    entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test"
    )


def _register_nothing(entity_registry: er.EntityRegistry) -> None:
    """Register nothing."""


def _stored_state_item(**kwargs: Any) -> dict[str, Any]:
    """Return a serialized stored state of test.test."""
    return {
        "state": {
            "entity_id": "test.test",
            "state": "stored",
            "attributes": {},
            "last_changed": "2026-01-01T00:00:00+00:00",
            "last_updated": "2026-01-01T00:00:00+00:00",
        },
        "extra_data": {"count": 3},
        "last_seen": dt_util.utcnow().isoformat(),
        **kwargs,
    }


@pytest.mark.parametrize(
    ("register", "entity_class", "add_entity", "expected_last_states"),
    [
        pytest.param(
            _register_test_entity,
            _RenameRestoreEntity,
            _async_add_rename_entity,
            [],
            id="registry_entry",
        ),
        pytest.param(
            _register_nothing,
            _NoUniqueIdRestoreEntity,
            _async_add_no_registry_entity,
            ["test.test"],
            id="no_registry_entry",
        ),
    ],
)
async def test_load_stored_state_without_entity_registry_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    register: Callable[[er.EntityRegistry], None],
    entity_class: type[_RenameRestoreEntity],
    add_entity: Callable[
        [HomeAssistant, er.EntityRegistry, _RenameRestoreEntity],
        Coroutine[Any, Any, MockEntityPlatform],
    ],
    expected_last_states: list[str],
) -> None:
    """Test loading a state stored before indexing by entity registry id."""
    register(entity_registry)
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": [_stored_state_item()],
    }
    data = async_get(hass)
    await data.async_load()

    assert list(data.last_states) == expected_last_states
    assert len(data.last_states_by_entity_registry_id) == 1 - len(expected_last_states)

    entity = entity_class()
    await add_entity(hass, entity_registry, entity)
    assert entity.restored == [("test.test", "stored", {"count": 3})]


async def test_load_stored_state_without_registry_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test a state stored without a registry entry is not claimed on load."""
    _register_test_entity(entity_registry)
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": [_stored_state_item(entity_registry_id=None)],
    }
    data = async_get(hass)
    await data.async_load()

    assert list(data.last_states) == ["test.test"]
    assert not data.last_states_by_entity_registry_id

    entity = _RenameRestoreEntity()
    await _async_add_rename_entity(hass, entity_registry, entity)
    assert entity.restored == [("test.test", None, None)]


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        pytest.param("test.registered", "by_registry_id", id="registry_entry"),
        pytest.param("test.registered_leftover", None, id="registry_entry_leftover"),
        pytest.param("test.unregistered", "unregistered", id="no_registry_entry"),
        pytest.param("test.unregistered_foreign", None, id="no_registry_entry_foreign"),
    ],
)
async def test_async_get_stored_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    expected: str | None,
) -> None:
    """Test which stored state is returned for an entity."""
    for object_id in ("registered", "registered_leftover"):
        entity_registry.async_get_or_create(
            "test", "test_platform", object_id, suggested_object_id=object_id
        )
    registered_id = entity_registry.async_get("test.registered").id
    data = async_get(hass)
    now = dt_util.utcnow()

    data.last_states_by_entity_registry_id[registered_id] = StoredState(
        State("test.registered", "by_registry_id"), None, now, registered_id
    )
    # Stored by entity_id after the registry entry was created
    data.last_states["test.registered"] = StoredState(
        State("test.registered", "leftover"), None, now
    )
    data.last_states["test.registered_leftover"] = StoredState(
        State("test.registered_leftover", "leftover"), None, now
    )
    data.last_states["test.unregistered"] = StoredState(
        State("test.unregistered", "unregistered"), None, now
    )
    # Stored by a registry entry which has since been removed
    data.last_states_by_entity_registry_id["removed"] = StoredState(
        State("test.unregistered_foreign", "foreign"), None, now, "removed"
    )

    stored_state = data.async_get_stored_state(entity_id)

    assert (stored_state.state.state if stored_state else None) == expected


async def test_async_get_stored_state_entity_id_changed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the stored state follows a changed entity_id."""
    registry_entry = entity_registry.async_get_or_create(
        "test", "test_platform", "5678", suggested_object_id="test2"
    )
    data = async_get(hass)
    now = dt_util.utcnow()
    context = Context()
    extra_data = _CounterExtraData(3)
    state = State(
        "test.test",
        "on",
        {"attr": "value"},
        last_changed=now - timedelta(hours=2),
        last_reported=now - timedelta(minutes=1),
        last_updated=now - timedelta(hours=1),
        context=context,
    )
    data.last_states_by_entity_registry_id[registry_entry.id] = StoredState(
        state, extra_data, now, registry_entry.id
    )

    stored_state = data.async_get_stored_state("test.test2")

    assert stored_state is data.last_states_by_entity_registry_id[registry_entry.id]
    assert stored_state.extra_data is extra_data
    assert stored_state.last_seen == now
    assert stored_state.state.as_dict() == {
        **state.as_dict(),
        "entity_id": "test.test2",
    }
    assert stored_state.state.context is context
