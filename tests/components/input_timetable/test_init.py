"""The tests for the input timetable component."""
import datetime

import pytest

from homeassistant.components.input_timetable import (
    ATTR_STATE,
    ATTR_TIME,
    ATTR_TIMETABLE,
    DOMAIN,
    SERVICE_RECONFIG,
    SERVICE_RELOAD,
    SERVICE_RESET,
    SERVICE_SET,
    SERVICE_UNSET,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, CoreState, State
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

# pylint: disable=protected-access
from tests.async_mock import patch
from tests.common import mock_restore_cache


@pytest.fixture(name="storage_setup")
def storage_setup_fixture(hass, hass_storage):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def call_set(hass, entity_id, time, state):
    """Add a state change event."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: time, ATTR_STATE: state},
        blocking=True,
    )


async def call_unset(hass, entity_id, time):
    """Remove a state change."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UNSET,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: time},
        blocking=True,
    )


async def call_reset(hass, entity_id):
    """Remove all state changes."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )


async def call_reconfig(hass, entity_id, config):
    """Override the timetable with the new list."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RECONFIG,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIMETABLE: config},
        blocking=True,
    )


async def test_load_from_storage(hass, storage_setup):
    """Test set up from storage."""
    assert await storage_setup()

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"


async def test_editable_state_attribute(hass, storage_setup):
    """Test editable attribute."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": {ATTR_NAME: "from yaml"}}})

    state = hass.states.get(f"{DOMAIN}.from_storage")
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from storage"
    assert state.attributes[ATTR_EDITABLE]

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.attributes[ATTR_FRIENDLY_NAME] == "from yaml"
    assert not state.attributes[ATTR_EDITABLE]


async def test_set(hass, caplog):
    """Test set method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_timetable.test"

    test_cases = [
        (
            "single",
            [("01:02:03", STATE_ON)],
            [
                {
                    ATTR_TIME: "01:02:03",
                    ATTR_STATE: STATE_ON,
                },
            ],
        ),
        (
            "multiple",
            [("04:05:06", STATE_ON), ("01:02:03", STATE_OFF)],
            [
                {
                    ATTR_TIME: "01:02:03",
                    ATTR_STATE: STATE_OFF,
                },
                {
                    ATTR_TIME: "04:05:06",
                    ATTR_STATE: STATE_ON,
                },
            ],
        ),
        (
            "override",
            [("01:02:03", STATE_ON), ("01:02:03", STATE_OFF)],
            [
                {
                    ATTR_TIME: "01:02:03",
                    ATTR_STATE: STATE_OFF,
                },
            ],
        ),
    ]

    for test_case in test_cases:
        await call_reset(hass, entity_id)
        for event in test_case[1]:
            time = datetime.time.fromisoformat(event[0])
            state = event[1]
            await call_set(hass, entity_id, time, state)
        state = hass.states.get(entity_id)
        assert (
            state.attributes[ATTR_TIMETABLE] == test_case[2]
        ), f"'{test_case[0]}' test case failed: timetable is '{state.attributes[ATTR_TIMETABLE]}' but expecting '{test_case[2]}''"


async def test_unset(hass, caplog):
    """Test unset method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_timetable.test"

    test_cases = [
        (
            "single",
            [("01:02:03", STATE_ON)],
            "01:02:03",
            [],
        ),
        (
            "multiple",
            [("04:05:06", STATE_ON), ("01:02:03", STATE_OFF)],
            "04:05:06",
            [
                {
                    ATTR_TIME: "01:02:03",
                    ATTR_STATE: STATE_OFF,
                },
            ],
        ),
        (
            "none",
            [("01:02:03", STATE_ON)],
            "04:05:06",
            [
                {
                    ATTR_TIME: "01:02:03",
                    ATTR_STATE: STATE_ON,
                },
            ],
        ),
    ]

    for test_case in test_cases:
        await call_reset(hass, entity_id)
        for event in test_case[1]:
            time = datetime.time.fromisoformat(event[0])
            state = event[1]
            await call_set(hass, entity_id, time, state)
        time = datetime.time.fromisoformat(test_case[2])
        await call_unset(hass, entity_id, time)
        state = hass.states.get(entity_id)
        assert (
            state.attributes[ATTR_TIMETABLE] == test_case[3]
        ), f"'{test_case[0]}' test case failed: timetable is '{state.attributes[ATTR_TIMETABLE]}' but expecting '{test_case[3]}''"


async def test_reset(hass, caplog):
    """Test reset method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_timetable.test"
    await call_set(hass, entity_id, "01:02:03", STATE_ON)
    await call_set(hass, entity_id, "04:05:06", STATE_OFF)
    await call_set(hass, entity_id, "07:08:09", STATE_ON)
    await call_set(hass, entity_id, "10:11:12", STATE_OFF)
    assert len(hass.states.get(entity_id).attributes[ATTR_TIMETABLE]) == 4
    await call_reset(hass, entity_id)
    assert len(hass.states.get(entity_id).attributes[ATTR_TIMETABLE]) == 0


async def test_reconfig(hass, caplog):
    """Test reconfig method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_timetable.test"
    await call_set(hass, entity_id, "01:02:03", STATE_ON)
    assert len(hass.states.get(entity_id).attributes[ATTR_TIMETABLE]) == 1
    await call_reconfig(
        hass,
        entity_id,
        [
            {ATTR_TIME: "07:08:09", ATTR_STATE: STATE_OFF},
            {ATTR_TIME: "04:05:06", ATTR_STATE: STATE_ON},
        ],
    )
    assert len(hass.states.get(entity_id).attributes[ATTR_TIMETABLE]) == 2
    assert (
        hass.states.get(entity_id).attributes[ATTR_TIMETABLE][0][ATTR_TIME]
        == "04:05:06"
    )


async def test_state(hass, caplog):
    """Test state attribute."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_timetable.test"

    assert hass.states.get(entity_id).state == STATE_OFF

    now = datetime.datetime.now().replace(microsecond=0)
    in_5_minutes = now + datetime.timedelta(minutes=5)
    in_10_minutes = now + datetime.timedelta(minutes=10)
    previous_10_minutes = now + datetime.timedelta(minutes=-10)
    previous_5_minutes = now + datetime.timedelta(minutes=-5)

    await call_set(hass, entity_id, previous_5_minutes.time().isoformat(), STATE_ON)
    assert hass.states.get(entity_id).state == STATE_ON
    await call_reset(hass, entity_id)

    await call_set(hass, entity_id, in_5_minutes.time().isoformat(), STATE_ON)
    assert hass.states.get(entity_id).state == STATE_ON
    await call_reset(hass, entity_id)

    await call_set(hass, entity_id, previous_10_minutes.time().isoformat(), STATE_ON)
    await call_set(hass, entity_id, previous_5_minutes.time().isoformat(), STATE_OFF)
    assert hass.states.get(entity_id).state == STATE_OFF
    await call_reset(hass, entity_id)

    await call_set(hass, entity_id, in_5_minutes.time().isoformat(), STATE_ON)
    await call_set(hass, entity_id, in_10_minutes.time().isoformat(), STATE_OFF)
    assert hass.states.get(entity_id).state == STATE_OFF
    await call_reset(hass, entity_id)

    await call_set(hass, entity_id, previous_5_minutes.time().isoformat(), STATE_ON)
    await call_set(hass, entity_id, in_5_minutes.time().isoformat(), STATE_OFF)
    assert hass.states.get(entity_id).state == STATE_ON
    await call_reset(hass, entity_id)


async def test_state_update(hass, caplog):
    """Test next update time."""
    with patch(
        "homeassistant.helpers.event.async_track_point_in_time"
    ) as async_track_point_in_time:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
        entity_id = f"{DOMAIN}.test"

        now = datetime.datetime.now().replace(microsecond=0)
        in_5_minutes = now + datetime.timedelta(minutes=5)
        in_10_minutes = now + datetime.timedelta(minutes=10)
        previous_5_minutes = now + datetime.timedelta(minutes=-5)
        previous_10_minutes = now + datetime.timedelta(minutes=-10)

        # No events => no updates.
        assert async_track_point_in_time.call_count == 0

        # One event => no updates.
        await call_set(hass, entity_id, in_5_minutes.time(), STATE_ON)
        assert async_track_point_in_time.call_count == 0
        await call_reset(hass, entity_id)

        # Between 2 events.
        await call_set(hass, entity_id, previous_5_minutes.time(), STATE_ON)
        await call_set(hass, entity_id, in_5_minutes.time(), STATE_OFF)
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == in_5_minutes
        await call_reset(hass, entity_id)

        # After any event.
        await call_set(hass, entity_id, previous_10_minutes.time(), STATE_ON)
        await call_set(hass, entity_id, previous_5_minutes.time(), STATE_OFF)
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == previous_10_minutes + datetime.timedelta(days=1)
        await call_reset(hass, entity_id)

        # Before any event.
        await call_set(hass, entity_id, in_5_minutes.time(), STATE_ON)
        await call_set(hass, entity_id, in_10_minutes.time(), STATE_OFF)
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == in_5_minutes
        await call_reset(hass, entity_id)


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    a_timetable = [
        {
            ATTR_TIME: "01:02:03",
            ATTR_STATE: STATE_ON,
        },
    ]
    b_timetable = [
        {
            ATTR_TIME: "07:08:09",
            ATTR_STATE: STATE_OFF,
        },
    ]
    mock_restore_cache(
        hass,
        (
            State("input_timetable.a", "", {ATTR_TIMETABLE: a_timetable}),
            State("input_timetable.b", "", {ATTR_TIMETABLE: b_timetable}),
        ),
    )

    hass.state = CoreState.starting

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"a": {}, "b": {}}},
    )

    state = hass.states.get("input_timetable.a")
    assert state
    assert state.attributes[ATTR_TIMETABLE] == a_timetable

    state = hass.states.get("input_timetable.b")
    assert state
    assert state.attributes[ATTR_TIMETABLE] == b_timetable


async def test_input_scheudle_context(hass, hass_admin_user):
    """Test that input_timetable context works."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"x": {}}})

    state = hass.states.get(f"{DOMAIN}.x")
    assert state is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_TIME: datetime.time.fromisoformat("01:02:03"),
            ATTR_STATE: STATE_ON,
        },
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get(f"{DOMAIN}.x")
    assert state2 is not None
    assert state.attributes[ATTR_TIMETABLE] != state2.attributes[ATTR_TIMETABLE]
    assert state2.context.user_id == hass_admin_user.id


async def test_reload(hass, hass_admin_user, hass_read_only_user):
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())
    ent_reg = await entity_registry.async_get_registry(hass)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": {ATTR_NAME: "before"},
                "test_3": {},
            }
        },
    )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get(f"{DOMAIN}.test_1")
    state_2 = hass.states.get(f"{DOMAIN}.test_2")
    state_3 = hass.states.get(f"{DOMAIN}.test_3")

    assert state_1 is not None
    assert state_1.attributes[ATTR_FRIENDLY_NAME] == "before"
    assert state_2 is None
    assert state_3 is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_1": {ATTR_NAME: "after"},
                "test_2": {},
            }
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get(f"{DOMAIN}.test_1")
    assert state_1.attributes[ATTR_FRIENDLY_NAME] == "after"
    state_2 = hass.states.get(f"{DOMAIN}.test_2")
    state_3 = hass.states.get(f"{DOMAIN}.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is None


async def test_setup_no_config(hass, hass_admin_user):
    """Test component setup with no config."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start == len(hass.states.async_entity_ids())


async def test_ws_list(hass, hass_ws_client, storage_setup):
    """Test listing via WS."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": {}}})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    storage_ent = "from_storage"
    yaml_ent = "from_yaml"
    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert storage_ent in result
    assert yaml_ent not in result
    assert result[storage_ent][ATTR_NAME] == "from storage"


async def test_ws_delete(hass, hass_ws_client, storage_setup):
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.{input_id}"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(input_entity_id)
    assert state is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is not None

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{input_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None


async def test_ws_create(hass, hass_ws_client, storage_setup):
    """Test create WS."""
    assert await storage_setup(items=[])

    input_id = "new_input"
    input_entity_id = f"{DOMAIN}.{input_id}"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(input_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/create",
            "name": "New Input",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == STATE_OFF
