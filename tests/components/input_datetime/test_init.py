"""Tests for the Input slider component."""
# pylint: disable=protected-access
import datetime
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.input_datetime import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_TIME,
    DOMAIN,
    SERVICE_RELOAD,
    SERVICE_SET_DATETIME,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, CoreState, State
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


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
    """Test default value if none has been set via inital or restore state."""
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

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "dt1": {"has_time": False, "has_date": True, "initial": "2019-1-1"},
            }
        },
    )

    assert count_start + 1 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("input_datetime.dt1")
    state_2 = hass.states.get("input_datetime.dt2")

    dt_obj = datetime.datetime(2019, 1, 1, 0, 0)
    assert state_1 is not None
    assert state_2 is None
    assert str(dt_obj.date()) == state_1.state

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
        with patch("homeassistant.config.find_config_file", return_value=""):
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

    dt_obj = datetime.datetime(2019, 1, 1, 23, 32)
    assert state_1 is not None
    assert state_2 is not None
    assert str(dt_obj.time()) == state_1.state
    assert str(datetime.datetime(1970, 1, 1, 0, 0)) == state_2.state
