"""Tests for the Risco event sensors."""
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.risco import (
    LAST_EVENT_TIMESTAMP_KEY,
    CannotConnectError,
    UnauthorizedError,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_IDS = {
    "Alarm": "sensor.risco_test_site_name_alarm_events",
    "Status": "sensor.risco_test_site_name_status_events",
    "Trouble": "sensor.risco_test_site_name_trouble_events",
    "Other": "sensor.risco_test_site_name_other_events",
}

TEST_EVENTS = [
    MagicMock(
        time="2020-09-02T10:00:00Z",
        category_id=4,
        category_name="System Status",
        type_id=16,
        type_name="disarmed",
        name="'user' disarmed 'partition'",
        text="",
        partition_id=0,
        zone_id=None,
        user_id=3,
        group=None,
        priority=2,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T09:00:00Z",
        category_id=7,
        category_name="Troubles",
        type_id=36,
        type_name="service needed",
        name="Device Fault",
        text="Service is needed.",
        partition_id=None,
        zone_id=None,
        user_id=None,
        group=None,
        priority=1,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T08:00:00Z",
        category_id=2,
        category_name="Alarms",
        type_id=3,
        type_name="triggered",
        name="Alarm is on",
        text="Yes it is.",
        partition_id=0,
        zone_id=1,
        user_id=None,
        group=None,
        priority=0,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T07:00:00Z",
        category_id=4,
        category_name="System Status",
        type_id=119,
        type_name="group arm",
        name="You armed a group",
        text="",
        partition_id=0,
        zone_id=None,
        user_id=1,
        group="C",
        priority=2,
        raw={},
    ),
    MagicMock(
        time="2020-09-02T06:00:00Z",
        category_id=8,
        category_name="Made up",
        type_id=200,
        type_name="also made up",
        name="really made up",
        text="",
        partition_id=2,
        zone_id=None,
        user_id=1,
        group=None,
        priority=2,
        raw={},
    ),
]

CATEGORIES_TO_EVENTS = {
    "Alarm": 2,
    "Status": 0,
    "Trouble": 1,
    "Other": 4,
}


@pytest.fixture
def _no_zones_and_partitions():
    with patch(
        "homeassistant.components.risco.RiscoLocal.zones",
        new_callable=PropertyMock(return_value=[]),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.partitions",
        new_callable=PropertyMock(return_value=[]),
    ):
        yield


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_login(
    hass: HomeAssistant, login_with_error, cloud_config_entry
) -> None:
    """Test error on login."""
    await hass.config_entries.async_setup(cloud_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)


def _check_state(hass, category, entity_id):
    event_index = CATEGORIES_TO_EVENTS[category]
    event = TEST_EVENTS[event_index]
    state = hass.states.get(entity_id)
    assert state.state == dt_util.parse_datetime(event.time).isoformat()
    assert state.attributes["category_id"] == event.category_id
    assert state.attributes["category_name"] == event.category_name
    assert state.attributes["type_id"] == event.type_id
    assert state.attributes["type_name"] == event.type_name
    assert state.attributes["name"] == event.name
    assert state.attributes["text"] == event.text
    assert state.attributes["partition_id"] == event.partition_id
    assert state.attributes["zone_id"] == event.zone_id
    assert state.attributes["user_id"] == event.user_id
    assert state.attributes["group"] == event.group
    assert state.attributes["priority"] == event.priority
    assert state.attributes["raw"] == event.raw
    if event_index == 2:
        assert state.attributes["zone_entity_id"] == "binary_sensor.zone_1"
    else:
        assert "zone_entity_id" not in state.attributes


@pytest.fixture
def _set_utc_time_zone(hass):
    hass.config.set_time_zone("UTC")


@pytest.fixture
def _save_mock():
    with patch(
        "homeassistant.components.risco.Store.async_save",
    ) as save_mock:
        yield save_mock


@pytest.mark.parametrize("events", [TEST_EVENTS])
async def test_cloud_setup(
    hass: HomeAssistant,
    two_zone_cloud,
    _set_utc_time_zone,
    _save_mock,
    setup_risco_cloud,
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    for id in ENTITY_IDS.values():
        assert registry.async_is_registered(id)

    _save_mock.assert_awaited_once_with({LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time})
    for category, entity_id in ENTITY_IDS.items():
        _check_state(hass, category, entity_id)

    with patch(
        "homeassistant.components.risco.RiscoCloud.get_events", return_value=[]
    ) as events_mock, patch(
        "homeassistant.components.risco.Store.async_load",
        return_value={LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time},
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=65))
        await hass.async_block_till_done()
        events_mock.assert_awaited_once_with(TEST_EVENTS[0].time, 10)

    for category, entity_id in ENTITY_IDS.items():
        _check_state(hass, category, entity_id)


async def test_local_setup(
    hass: HomeAssistant, setup_risco_local, _no_zones_and_partitions
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)
