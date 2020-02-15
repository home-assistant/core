"""Tests for the Input slider component."""
# pylint: disable=protected-access
import datetime
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.input_datetime import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_EDITABLE,
    ATTR_TIME,
    CONF_HAS_DATE,
    CONF_HAS_TIME,
    CONF_ID,
    CONF_INITIAL,
    CONF_NAME,
    DEFAULT_TIME,
    DOMAIN,
    SERVICE_RELOAD,
    SERVICE_SET_DATETIME,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_NAME
from homeassistant.core import Context, CoreState, State
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache

INITIAL_DATE = "2020-01-10"
INITIAL_TIME = "23:45:56"
INITIAL_DATETIME = f"{INITIAL_DATE} {INITIAL_TIME}"


@pytest.fixture
def storage_setup(hass, hass_storage):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            CONF_ID: "from_storage",
                            CONF_NAME: "datetime from storage",
                            CONF_INITIAL: INITIAL_DATETIME,
                            CONF_HAS_DATE: True,
                            CONF_HAS_TIME: True,
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


async def async_set_date_and_time(hass, entity_id, dt_value):
    """Set date and / or time of input_datetime."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DATETIME,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_DATE: dt_value.date(),
            ATTR_TIME: dt_value.time(),
        },
        blocking=True,
    )


async def async_set_datetime(hass, entity_id, dt_value):
    """Set date and / or time of input_datetime."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DATETIME,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATETIME: dt_value},
        blocking=True,
    )


async def test_invalid_configs(hass):
    """Test config."""
    invalid_configs = [
        None,
        {},
        {"name with space": None},
        {"test_no_value": {"has_time": False, "has_date": False}},
    ]
    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_set_datetime(hass):
    """Test set_datetime method using date & time."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_datetime": {"has_time": True, "has_date": True}}}
    )

    entity_id = "input_datetime.test_datetime"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46, 30)

    await async_set_date_and_time(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(dt_obj)
    assert state.attributes["has_time"]
    assert state.attributes["has_date"]

    assert state.attributes["year"] == 2017
    assert state.attributes["month"] == 9
    assert state.attributes["day"] == 7
    assert state.attributes["hour"] == 19
    assert state.attributes["minute"] == 46
    assert state.attributes["second"] == 30
    assert state.attributes["timestamp"] == dt_obj.timestamp()


async def test_set_datetime_2(hass):
    """Test set_datetime method using datetime."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_datetime": {"has_time": True, "has_date": True}}}
    )

    entity_id = "input_datetime.test_datetime"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46, 30)

    await async_set_datetime(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(dt_obj)
    assert state.attributes["has_time"]
    assert state.attributes["has_date"]

    assert state.attributes["year"] == 2017
    assert state.attributes["month"] == 9
    assert state.attributes["day"] == 7
    assert state.attributes["hour"] == 19
    assert state.attributes["minute"] == 46
    assert state.attributes["second"] == 30
    assert state.attributes["timestamp"] == dt_obj.timestamp()


async def test_set_datetime_time(hass):
    """Test set_datetime method with only time."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_time": {"has_time": True, "has_date": False}}}
    )

    entity_id = "input_datetime.test_time"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46, 30)
    time_portion = dt_obj.time()

    await async_set_date_and_time(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(time_portion)
    assert state.attributes["has_time"]
    assert not state.attributes["has_date"]

    assert state.attributes["timestamp"] == (19 * 3600) + (46 * 60) + 30


async def test_set_invalid(hass):
    """Test set_datetime method with only time."""
    initial = "2017-01-01"
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_date": {"has_time": False, "has_date": True, "initial": initial}
            }
        },
    )

    entity_id = "input_datetime.test_date"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    time_portion = dt_obj.time()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "input_datetime",
            "set_datetime",
            {"entity_id": "test_date", "time": time_portion},
        )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == initial


async def test_set_invalid_2(hass):
    """Test set_datetime method with date and datetime."""
    initial = "2017-01-01"
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_date": {"has_time": False, "has_date": True, "initial": initial}
            }
        },
    )

    entity_id = "input_datetime.test_date"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    time_portion = dt_obj.time()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "input_datetime",
            "set_datetime",
            {"entity_id": "test_date", "time": time_portion, "datetime": dt_obj},
        )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == initial


async def test_set_datetime_date(hass):
    """Test set_datetime method with only date."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_date": {"has_time": False, "has_date": True}}}
    )

    entity_id = "input_datetime.test_date"

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    date_portion = dt_obj.date()

    await async_set_date_and_time(hass, entity_id, dt_obj)

    state = hass.states.get(entity_id)
    assert state.state == str(date_portion)
    assert not state.attributes["has_time"]
    assert state.attributes["has_date"]

    date_dt_obj = datetime.datetime(2017, 9, 7)
    assert state.attributes["timestamp"] == date_dt_obj.timestamp()


async def test_restore_state(hass):
    """Ensure states are restored on startup."""
    mock_restore_cache(
        hass,
        (
            State("input_datetime.test_time", "19:46:00"),
            State("input_datetime.test_date", "2017-09-07"),
            State("input_datetime.test_datetime", "2017-09-07 19:46:00"),
            State("input_datetime.test_bogus_data", "this is not a date"),
        ),
    )

    hass.state = CoreState.starting

    initial = datetime.datetime(2017, 1, 1, 23, 42)

    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_time": {"has_time": True, "has_date": False},
                "test_date": {"has_time": False, "has_date": True},
                "test_datetime": {"has_time": True, "has_date": True},
                "test_bogus_data": {
                    "has_time": True,
                    "has_date": True,
                    "initial": str(initial),
                },
            }
        },
    )

    dt_obj = datetime.datetime(2017, 9, 7, 19, 46)
    state_time = hass.states.get("input_datetime.test_time")
    assert state_time.state == str(dt_obj.time())

    state_date = hass.states.get("input_datetime.test_date")
    assert state_date.state == str(dt_obj.date())

    state_datetime = hass.states.get("input_datetime.test_datetime")
    assert state_datetime.state == str(dt_obj)

    state_bogus = hass.states.get("input_datetime.test_bogus_data")
    assert state_bogus.state == str(initial)


async def test_default_value(hass):
    """Test default value if none has been set via initial or restore state."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_time": {"has_time": True, "has_date": False},
                "test_date": {"has_time": False, "has_date": True},
                "test_datetime": {"has_time": True, "has_date": True},
            }
        },
    )

    dt_obj = datetime.datetime(1970, 1, 1, 0, 0)
    state_time = hass.states.get("input_datetime.test_time")
    assert state_time.state == str(dt_obj.time())
    assert state_time.attributes.get("timestamp") is not None

    state_date = hass.states.get("input_datetime.test_date")
    assert state_date.state == str(dt_obj.date())
    assert state_date.attributes.get("timestamp") is not None

    state_datetime = hass.states.get("input_datetime.test_datetime")
    assert state_datetime.state == str(dt_obj)
    assert state_datetime.attributes.get("timestamp") is not None


async def test_input_datetime_context(hass, hass_admin_user):
    """Test that input_datetime context works."""
    assert await async_setup_component(
        hass, "input_datetime", {"input_datetime": {"only_date": {"has_date": True}}}
    )

    state = hass.states.get("input_datetime.only_date")
    assert state is not None

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {"entity_id": state.entity_id, "date": "2018-01-02"},
        True,
        Context(user_id=hass_admin_user.id),
    )

    state2 = hass.states.get("input_datetime.only_date")
    assert state2 is not None
    assert state.state != state2.state
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
                "dt1": {"has_time": False, "has_date": True, "initial": "2019-1-1"},
                "dt3": {CONF_HAS_TIME: True, CONF_HAS_DATE: True},
            }
        },
    )

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_datetime.dt1")
    state_2 = hass.states.get("input_datetime.dt2")
    state_3 = hass.states.get("input_datetime.dt3")

    dt_obj = datetime.datetime(2019, 1, 1, 0, 0)
    assert state_1 is not None
    assert state_2 is None
    assert state_3 is not None
    assert str(dt_obj.date()) == state_1.state
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt1") == f"{DOMAIN}.dt1"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt2") is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt3") == f"{DOMAIN}.dt3"

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "dt1": {"has_time": True, "has_date": False, "initial": "23:32"},
                "dt2": {"has_time": True, "has_date": True},
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

    state_1 = hass.states.get("input_datetime.dt1")
    state_2 = hass.states.get("input_datetime.dt2")
    state_3 = hass.states.get("input_datetime.dt3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None
    assert str(DEFAULT_TIME) == state_1.state
    assert str(datetime.datetime(1970, 1, 1, 0, 0)) == state_2.state

    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt1") == f"{DOMAIN}.dt1"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt2") == f"{DOMAIN}.dt2"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "dt3") is None


async def test_load_from_storage(hass, storage_setup):
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.datetime_from_storage")
    assert state.state == INITIAL_DATETIME
    assert state.attributes.get(ATTR_EDITABLE)


async def test_editable_state_attribute(hass, storage_setup):
    """Test editable attribute."""
    assert await storage_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_HAS_DATE: True,
                    CONF_HAS_TIME: True,
                    CONF_NAME: "yaml datetime",
                    CONF_INITIAL: "2001-01-02 12:34:56",
                }
            }
        }
    )

    state = hass.states.get(f"{DOMAIN}.datetime_from_storage")
    assert state.state == INITIAL_DATETIME
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.state == "2001-01-02 12:34:56"
    assert not state.attributes[ATTR_EDITABLE]


async def test_ws_list(hass, hass_ws_client, storage_setup):
    """Test listing via WS."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": {CONF_HAS_DATE: True}}})

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
    assert result[storage_ent][ATTR_NAME] == "datetime from storage"


async def test_ws_delete(hass, hass_ws_client, storage_setup):
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.datetime_from_storage"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(input_entity_id)
    assert state is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) == input_entity_id

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{input_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) is None


async def test_update(hass, hass_ws_client, storage_setup):
    """Test updating min/max updates the state."""

    assert await storage_setup()

    input_id = "from_storage"
    input_entity_id = f"{DOMAIN}.datetime_from_storage"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(input_entity_id)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "datetime from storage"
    assert state.state == INITIAL_DATETIME
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, input_id) == input_entity_id

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{input_id}",
            ATTR_NAME: "even newer name",
            CONF_HAS_DATE: False,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == INITIAL_TIME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "even newer name"


async def test_ws_create(hass, hass_ws_client, storage_setup):
    """Test create WS."""
    assert await storage_setup(items=[])

    input_id = "new_datetime"
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
            CONF_NAME: "New DateTime",
            CONF_INITIAL: "1991-01-02 01:02:03",
            CONF_HAS_DATE: True,
            CONF_HAS_TIME: True,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(input_entity_id)
    assert state.state == "1991-01-02 01:02:03"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "New DateTime"
    assert state.attributes[ATTR_EDITABLE]


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
