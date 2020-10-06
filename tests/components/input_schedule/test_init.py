"""The tests for the Input schedule component."""
import datetime

import pytest

from homeassistant.components.input_schedule import (
    ATTR_END,
    ATTR_ON_PERIODS,
    ATTR_START,
    DOMAIN,
    SERVICE_RELOAD,
    SERVICE_RESET,
    SERVICE_SET_OFF,
    SERVICE_SET_ON,
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


async def set_on(hass, entity_id, start, end):
    """Add an on period."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_START: start, ATTR_END: end},
        blocking=True,
    )


async def set_off(hass, entity_id, start, end):
    """Add an off period."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_OFF,
        {ATTR_ENTITY_ID: entity_id, ATTR_START: start, ATTR_END: end},
        blocking=True,
    )


async def reset(hass, entity_id):
    """Remove all on periods."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET,
        {ATTR_ENTITY_ID: entity_id},
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


async def test_set_on(hass, caplog):
    """Test set_on method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_schedule.test"

    test_cases = [
        (
            "simple",
            [("01:02:03", "04:05:06")],
            [
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "04:05:06",
                },
            ],
        ),
        (
            "multiple",
            (("10:00:00", "11:00:00"), ("02:00:00", "03:00:00")),
            [
                {
                    ATTR_START: "02:00:00",
                    ATTR_END: "03:00:00",
                },
                {
                    ATTR_START: "10:00:00",
                    ATTR_END: "11:00:00",
                },
            ],
        ),
        (
            "overlapping",
            (("01:00:00", "03:00:00"), ("02:00:00", "04:00:00")),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "04:00:00",
                },
            ],
        ),
        (
            "adjusted",
            (("01:00:00", "02:00:00"), ("02:00:00", "03:00:00")),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "03:00:00",
                },
            ],
        ),
        (
            "subset",
            (("01:00:00", "04:00:00"), ("02:00:00", "03:00:00")),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "04:00:00",
                },
            ],
        ),
        (
            "superset",
            (("02:00:00", "03:00:00"), ("01:00:00", "04:00:00")),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "04:00:00",
                },
            ],
        ),
        (
            "merge",
            (
                ("01:00:00", "02:00:00"),
                ("03:00:00", "04:00:00"),
                ("02:00:00", "03:00:00"),
            ),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "04:00:00",
                },
            ],
        ),
    ]

    for test_case in test_cases:
        await reset(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

        for period in test_case[1]:
            start = datetime.time.fromisoformat(period[0])
            end = datetime.time.fromisoformat(period[1])
            await set_on(hass, entity_id, start, end)

        state = hass.states.get(entity_id)
        assert (
            state.attributes[ATTR_ON_PERIODS] == test_case[2]
        ), f"'{test_case[0]}' test case failed: state is '{state.attributes[ATTR_ON_PERIODS]}' but expecting '{test_case[2]}''"


async def test_set_off(hass, caplog):
    """Test set_off method."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_schedule.test"

    test_cases = [
        (
            "simple",
            [("01:02:03", "04:05:06")],
            ("02:03:04", "04:05:06"),
            [
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "02:03:04",
                },
            ],
        ),
        (
            "superset",
            [("01:00:00", "05:00:00")],
            ("00:00:00", "10:00:00"),
            [],
        ),
        (
            "subset",
            [("01:00:00", "05:00:00")],
            ("02:00:00", "04:00:00"),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "02:00:00",
                },
                {
                    ATTR_START: "04:00:00",
                    ATTR_END: "05:00:00",
                },
            ],
        ),
        (
            "adjusted",
            [("01:00:00", "02:00:00")],
            ("02:00:00", "03:00:00"),
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "02:00:00",
                },
            ],
        ),
    ]

    for test_case in test_cases:
        await reset(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

        for on_period in test_case[1]:
            start = datetime.time.fromisoformat(on_period[0])
            end = datetime.time.fromisoformat(on_period[1])
            await set_on(hass, entity_id, start, end)

        start = datetime.time.fromisoformat(test_case[2][0])
        end = datetime.time.fromisoformat(test_case[2][1])
        await set_off(hass, entity_id, start, end)

        state = hass.states.get(entity_id)
        assert (
            state.attributes[ATTR_ON_PERIODS] == test_case[3]
        ), f"'{test_case[0]}' test case failed: state is '{state.attributes[ATTR_ON_PERIODS]}' but expecting '{test_case[3]}''"


async def test_state(hass, caplog):
    """Test state attribute."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
    entity_id = "input_schedule.test"

    assert hass.states.get(entity_id).state == STATE_OFF

    now = datetime.datetime.now()
    in_2_minutes = now + datetime.timedelta(minutes=2)

    start = now.time()
    end = in_2_minutes.time()

    if end < start:
        # The rare case of day overlap - skip the test
        return

    await set_on(hass, entity_id, start, end)
    assert hass.states.get(entity_id).state == STATE_ON


async def test_state_update(hass, caplog):
    """Test next update time."""
    with patch(
        "homeassistant.helpers.event.async_track_point_in_time"
    ) as async_track_point_in_time:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test": {}}})
        entity_id = f"{DOMAIN}.test"

        # No update if there are no on periods.
        assert async_track_point_in_time.call_count == 0

        now = datetime.datetime.now().replace(microsecond=0)
        in_5_minutes = now + datetime.timedelta(minutes=5)
        in_10_minutes = now + datetime.timedelta(minutes=10)
        previous_5_minutes = now + datetime.timedelta(minutes=-5)
        next_midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1),
            datetime.time.fromisoformat("00:00:00"),
        )

        if in_10_minutes.time() < previous_5_minutes.time():
            # The rare case of day overlap - skip the test
            return

        # State is on => update is at the end of the range.
        await set_on(hass, entity_id, now.time(), in_5_minutes.time())
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == in_5_minutes

        # State if off => update is at the beginning of the next range.
        await reset(hass, entity_id)
        await set_on(hass, entity_id, in_5_minutes.time(), in_10_minutes.time())
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == in_5_minutes

        # State is off, and range is eariler in the day => update in midnight.
        await reset(hass, entity_id)
        await set_on(hass, entity_id, previous_5_minutes.time(), now.time())
        next_update = async_track_point_in_time.call_args[0][2]
        assert next_update == next_midnight


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    a_on_periods = [
        {
            ATTR_START: "01:02:03",
            ATTR_END: "02:03:04",
        },
    ]
    b_on_periods = [
        {
            ATTR_START: "07:08:09",
            ATTR_END: "10:11:12",
        },
    ]
    mock_restore_cache(
        hass,
        (
            State("input_schedule.a", "", {ATTR_ON_PERIODS: a_on_periods}),
            State("input_schedule.b", "", {ATTR_ON_PERIODS: b_on_periods}),
        ),
    )

    hass.state = CoreState.starting

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"a": {}, "b": {}}},
    )

    state = hass.states.get("input_schedule.a")
    assert state
    assert state.attributes[ATTR_ON_PERIODS] == a_on_periods

    state = hass.states.get("input_schedule.b")
    assert state
    assert state.attributes[ATTR_ON_PERIODS] == b_on_periods


async def test_input_scheudle_context(hass, hass_admin_user):
    """Test that input_schedule context works."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"x": {}}})

    state = hass.states.get(f"{DOMAIN}.x")
    assert state is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ON,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_START: datetime.time.fromisoformat("01:02:03"),
            ATTR_END: datetime.time.fromisoformat("04:05:06"),
        },
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get(f"{DOMAIN}.x")
    assert state2 is not None
    assert state.attributes[ATTR_ON_PERIODS] != state2.attributes[ATTR_ON_PERIODS]
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
