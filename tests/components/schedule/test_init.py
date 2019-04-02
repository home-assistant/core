"""The tests for the Schedule component."""
from unittest.mock import patch
from datetime import datetime
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import schedule
from homeassistant.helpers.storage import Store
from homeassistant.components.websocket_api.const import TYPE_RESULT


from tests.common import (async_mock_service,
                          async_fire_time_changed)


DOMAIN_CLIMATE = "climate"
DOMAIN_INPUT_BOOL = "input_boolean"
SERVICE_SET_TEMP = "set_temperature"
SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"

RULE_ALL_CLIMATE = {
    "active": True,
    "days": [True, True, True, True, True, True, True],
    "end": "9:00",
    "entity": "climate.fake",
    "start": "8:00",
    "value": 25
}
RULE_ALL_SWITCH = {
    "active": True,
    "days": [True, True, True, True, True, True, True],
    "end": "11:00",
    "entity": "input_boolean.fake",
    "start": "10:00",
    "value": True
}

RULE_TEST = {
    "active": True,
    "days": [True, True, False, True, True, True, True],
    "end": "12:00",
    "entity": "input_boolean.fake",
    "start": "10:00",
    "value": True
}


TEST_CONFIG = {
    schedule.DOMAIN: {"entities":
                      ["climate.fake",
                       "input_boolean.fake"]}}

TEST_DEFAULTS_BASE = {
    "climate.fake": 20,
    "input_boolean.fake": False
}
TEST_DEFAULTS_MOD = {
    "climate.fake": 21,
    "input_boolean.fake": True
}


def gen_storage_data(rules=[], defaults=TEST_DEFAULTS_BASE):
    """Generate test storage data."""
    return {
        "defaults": defaults,
        "rules": rules
    }


async def gen_storage(hass, rules=[], defaults=TEST_DEFAULTS_BASE):
    """Fill the mocked storage with test.."""
    store = Store(hass, schedule.STORAGE_VERSION,
                  schedule.STORAGE_KEY)
    await store.async_save(gen_storage_data(rules, defaults))


@pytest.fixture
def mock_services(hass):
    """Mock the services used by the schedule."""
    calls_set_temp = async_mock_service(
        hass, DOMAIN_CLIMATE, SERVICE_SET_TEMP)
    calls_turn_on = async_mock_service(
        hass, DOMAIN_INPUT_BOOL, SERVICE_TURN_ON)
    calls_turn_off = async_mock_service(
        hass, DOMAIN_INPUT_BOOL, SERVICE_TURN_OFF)
    yield [calls_set_temp, calls_turn_on, calls_turn_off]


def test_rule(hass):
    """Test the Rule subclass."""
    rule_a = schedule.Rule(RULE_TEST)
    assert rule_a.to_dict() == RULE_TEST
    assert rule_a.active is True
    assert rule_a.days == [True, True, False, True, True, True, True]
    assert rule_a.start == "10:00"
    assert rule_a.end == "12:00"
    assert rule_a.entity == "input_boolean.fake"
    assert rule_a.value is True

    assert rule_a.should_update(datetime(2019, 4, 1, 9, 59, 59)) is False
    assert rule_a.should_update(datetime(2019, 4, 1, 10, 00, 00)) is True
    assert rule_a.should_update(datetime(2019, 4, 1, 11, 00, 00)) is True
    assert rule_a.should_update(datetime(2019, 4, 1, 11, 59, 59)) is True
    assert rule_a.should_update(datetime(2019, 4, 1, 12, 00, 00)) is False
    assert rule_a.should_update(datetime(2019, 4, 3, 9, 59, 59)) is False
    assert rule_a.should_update(datetime(2019, 4, 3, 10, 00, 00)) is False

    rule_a._active = False
    assert rule_a.should_update(datetime(2019, 4, 1, 11, 00, 00)) is False


async def test_load_rules(hass, hass_storage, mock_services):
    """Test if the rules load correctly."""
    await gen_storage(hass, [RULE_ALL_CLIMATE, RULE_ALL_SWITCH],
                      TEST_DEFAULTS_MOD)

    assert await async_setup_component(hass, schedule.DOMAIN, TEST_CONFIG)
    await hass.async_start()
    await hass.async_block_till_done()

    m_schedule = hass.data[schedule.DOMAIN]
    assert m_schedule

    rules = m_schedule.rules
    assert len(rules) == 2

    assert rules[0].to_dict() == RULE_ALL_CLIMATE
    assert rules[1].to_dict() == RULE_ALL_SWITCH
    assert m_schedule.defaults == TEST_DEFAULTS_MOD


async def test_default_storage_created(hass, hass_storage, mock_services):
    """Test if the rules load correctly."""
    assert await async_setup_component(hass, schedule.DOMAIN, TEST_CONFIG)
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass_storage[schedule.STORAGE_KEY]["data"] == gen_storage_data()


async def test_schedule_exec(hass, hass_storage):
    """Test the execution of a schedule."""
    calls_temp = async_mock_service(
        hass, DOMAIN_CLIMATE, SERVICE_SET_TEMP)
    calls_turn_on = async_mock_service(
        hass, DOMAIN_INPUT_BOOL, SERVICE_TURN_ON)
    calls_turn_off = async_mock_service(
        hass, DOMAIN_INPUT_BOOL, SERVICE_TURN_OFF)

    now = datetime(2019, 4, 1, 7, 00, 00)

    await gen_storage(hass, [RULE_ALL_CLIMATE, RULE_ALL_SWITCH],
                      TEST_DEFAULTS_BASE)

    with patch("homeassistant.util.dt.now", return_value=now):
        assert await async_setup_component(
            hass, schedule.DOMAIN,
            TEST_CONFIG
        )
        await hass.async_start()
        await hass.async_block_till_done()

    now = datetime(2019, 4, 1, 8, 00, 00)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    now = datetime(2019, 4, 1, 9, 00, 00)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    now = datetime(2019, 4, 1, 10, 00, 00)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    now = datetime(2019, 4, 1, 12, 00, 00)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    assert len(calls_temp) == 5
    for x in range(5):
        assert calls_temp[x].data["entity_id"] == "climate.fake"
        assert calls_temp[x].data["temperature"] == 25 if x == 1 else 20
    assert len(calls_turn_on) == 1
    assert calls_turn_on[0].data["entity_id"] == "input_boolean.fake"
    assert len(calls_turn_off) == 4
    for x in range(4):
        assert calls_turn_off[x].data["entity_id"] == "input_boolean.fake"


async def test_ws_api(hass, hass_storage, hass_ws_client, mock_services):
    """Test the websocket api for the schedule."""
    await gen_storage(hass, [RULE_ALL_CLIMATE, RULE_ALL_SWITCH],
                      TEST_DEFAULTS_BASE)

    assert await async_setup_component(
        hass, schedule.DOMAIN,
        TEST_CONFIG
    )
    await hass.async_start()
    await hass.async_block_till_done()

    m_schedule = hass.data[schedule.DOMAIN]

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': "schedule/entities"
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['result']['entities'] == ["climate.fake", "input_boolean.fake"]

    await client.send_json({
        'id': 6,
        'type': "schedule/rules"
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    assert msg['id'] == 6
    assert msg['type'] == TYPE_RESULT
    data = msg['result']['rules']
    assert data[0] == RULE_ALL_CLIMATE
    assert data[1] == RULE_ALL_SWITCH

    await client.send_json({
        'id': 7,
        'type': "schedule/clear"
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    assert msg['id'] == 7
    assert msg['type'] == TYPE_RESULT
    assert msg['result']['completed'] is True

    assert m_schedule.rules == []
    assert hass_storage[schedule.STORAGE_KEY]['data']['rules'] == []

    await client.send_json({
        'id': 8,
        'type': "schedule/save",
        'rules': [RULE_TEST]
    })
    msg = await client.receive_json()
    assert msg['success'] is True
    assert msg['id'] == 8
    assert msg['type'] == TYPE_RESULT
    assert msg['result']['completed'] is True

    assert len(m_schedule.rules) == 1
    assert m_schedule.rules[0].to_dict() == RULE_TEST
    assert hass_storage[schedule.STORAGE_KEY]['data']['rules'] == [RULE_TEST]
