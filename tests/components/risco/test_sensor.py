"""Tests for the Risco event sensors."""
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from homeassistant.components.risco import (
    LAST_EVENT_TIMESTAMP_KEY,
    CannotConnectError,
    UnauthorizedError,
)
from homeassistant.components.risco.const import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from .util import TEST_CONFIG, TEST_SITE_UUID, setup_risco
from .util import two_zone_alarm  # noqa: F401

from tests.common import MockConfigEntry, async_fire_time_changed

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


async def test_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)


async def test_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)


def _check_state(hass, category, entity_id):
    event_index = CATEGORIES_TO_EVENTS[category]
    event = TEST_EVENTS[event_index]
    state = hass.states.get(entity_id)
    assert state.state == event.time
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


async def test_setup(hass, two_zone_alarm):  # noqa: F811
    """Test entity setup."""
    registry = er.async_get(hass)

    for id in ENTITY_IDS.values():
        assert not registry.async_is_registered(id)

    with patch(
        "homeassistant.components.risco.RiscoAPI.site_uuid",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.Store.async_save",
    ) as save_mock:
        await setup_risco(hass, TEST_EVENTS)
        for id in ENTITY_IDS.values():
            assert registry.async_is_registered(id)

        save_mock.assert_awaited_once_with(
            {LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time}
        )
        for category, entity_id in ENTITY_IDS.items():
            _check_state(hass, category, entity_id)

    with patch(
        "homeassistant.components.risco.RiscoAPI.get_events", return_value=[]
    ) as events_mock, patch(
        "homeassistant.components.risco.Store.async_load",
        return_value={LAST_EVENT_TIMESTAMP_KEY: TEST_EVENTS[0].time},
    ):
        async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=65))
        await hass.async_block_till_done()
        events_mock.assert_awaited_once_with(TEST_EVENTS[0].time, 10)

    for category, entity_id in ENTITY_IDS.items():
        _check_state(hass, category, entity_id)
