"""The tests for the Demo vacuum platform."""
from datetime import timedelta

import pytest

from homeassistant.components import vacuum
from homeassistant.components.demo.vacuum import (
    DEMO_VACUUM_BASIC,
    DEMO_VACUUM_COMPLETE,
    DEMO_VACUUM_MINIMAL,
    DEMO_VACUUM_MOST,
    DEMO_VACUUM_NONE,
    DEMO_VACUUM_STATE,
    FAN_SPEEDS,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_COMMAND,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_PARAMS,
    ATTR_STATUS,
    DOMAIN,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import async_fire_time_changed, async_mock_service
from tests.components.vacuum import common

ENTITY_VACUUM_BASIC = f"{DOMAIN}.{DEMO_VACUUM_BASIC}".lower()
ENTITY_VACUUM_COMPLETE = f"{DOMAIN}.{DEMO_VACUUM_COMPLETE}".lower()
ENTITY_VACUUM_MINIMAL = f"{DOMAIN}.{DEMO_VACUUM_MINIMAL}".lower()
ENTITY_VACUUM_MOST = f"{DOMAIN}.{DEMO_VACUUM_MOST}".lower()
ENTITY_VACUUM_NONE = f"{DOMAIN}.{DEMO_VACUUM_NONE}".lower()
ENTITY_VACUUM_STATE = f"{DOMAIN}.{DEMO_VACUUM_STATE}".lower()


@pytest.fixture(autouse=True)
async def setup_demo_vacuum(hass):
    """Initialize setup demo vacuum."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "demo"}})
    await hass.async_block_till_done()


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test vacuum supported features."""
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 2047
    assert state.attributes.get(ATTR_STATUS) == "Charging"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) == "medium"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == FAN_SPEEDS
    assert state.state == STATE_OFF

    state = hass.states.get(ENTITY_VACUUM_MOST)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 219
    assert state.attributes.get(ATTR_STATUS) == "Charging"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == STATE_OFF

    state = hass.states.get(ENTITY_VACUUM_BASIC)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 195
    assert state.attributes.get(ATTR_STATUS) == "Charging"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == STATE_OFF

    state = hass.states.get(ENTITY_VACUUM_MINIMAL)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3
    assert state.attributes.get(ATTR_STATUS) is None
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == STATE_OFF

    state = hass.states.get(ENTITY_VACUUM_NONE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    assert state.attributes.get(ATTR_STATUS) is None
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == STATE_OFF

    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 13436
    assert state.state == STATE_DOCKED
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) == "medium"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == FAN_SPEEDS


async def test_methods(hass: HomeAssistant) -> None:
    """Test if methods call the services as expected."""
    hass.states.async_set(ENTITY_VACUUM_BASIC, STATE_ON)
    await hass.async_block_till_done()
    assert vacuum.is_on(hass, ENTITY_VACUUM_BASIC)

    hass.states.async_set(ENTITY_VACUUM_BASIC, STATE_OFF)
    await hass.async_block_till_done()
    assert not vacuum.is_on(hass, ENTITY_VACUUM_BASIC)

    await common.async_turn_on(hass, ENTITY_VACUUM_COMPLETE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_turn_off(hass, ENTITY_VACUUM_COMPLETE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_toggle(hass, ENTITY_VACUUM_COMPLETE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_start_pause(hass, ENTITY_VACUUM_COMPLETE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_start_pause(hass, ENTITY_VACUUM_COMPLETE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_stop(hass, ENTITY_VACUUM_COMPLETE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.attributes.get(ATTR_BATTERY_LEVEL) < 100
    assert state.attributes.get(ATTR_STATUS) != "Charging"

    await common.async_locate(hass, ENTITY_VACUUM_COMPLETE)
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert "I'm over here" in state.attributes.get(ATTR_STATUS)

    await common.async_return_to_base(hass, ENTITY_VACUUM_COMPLETE)
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert "Returning home" in state.attributes.get(ATTR_STATUS)

    await common.async_set_fan_speed(
        hass, FAN_SPEEDS[-1], entity_id=ENTITY_VACUUM_COMPLETE
    )
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.attributes.get(ATTR_FAN_SPEED) == FAN_SPEEDS[-1]

    await common.async_clean_spot(hass, entity_id=ENTITY_VACUUM_COMPLETE)
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert "spot" in state.attributes.get(ATTR_STATUS)
    assert state.state == STATE_ON

    await common.async_start(hass, ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_CLEANING

    await common.async_pause(hass, ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_PAUSED

    await common.async_stop(hass, ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_IDLE

    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.attributes.get(ATTR_BATTERY_LEVEL) < 100
    assert state.state != STATE_DOCKED

    await common.async_return_to_base(hass, ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_RETURNING

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_DOCKED

    await common.async_set_fan_speed(
        hass, FAN_SPEEDS[-1], entity_id=ENTITY_VACUUM_STATE
    )
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.attributes.get(ATTR_FAN_SPEED) == FAN_SPEEDS[-1]

    await common.async_clean_spot(hass, entity_id=ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state == STATE_CLEANING


async def test_unsupported_methods(hass: HomeAssistant) -> None:
    """Test service calls for unsupported vacuums."""
    hass.states.async_set(ENTITY_VACUUM_NONE, STATE_ON)
    await hass.async_block_till_done()
    assert vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    await common.async_turn_off(hass, ENTITY_VACUUM_NONE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    await common.async_stop(hass, ENTITY_VACUUM_NONE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    hass.states.async_set(ENTITY_VACUUM_NONE, STATE_OFF)
    await hass.async_block_till_done()
    assert not vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    await common.async_turn_on(hass, ENTITY_VACUUM_NONE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    await common.async_toggle(hass, ENTITY_VACUUM_NONE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    # Non supported methods:
    await common.async_start_pause(hass, ENTITY_VACUUM_NONE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_NONE)

    await common.async_locate(hass, ENTITY_VACUUM_NONE)
    state = hass.states.get(ENTITY_VACUUM_NONE)
    assert state.attributes.get(ATTR_STATUS) is None

    await common.async_return_to_base(hass, ENTITY_VACUUM_NONE)
    state = hass.states.get(ENTITY_VACUUM_NONE)
    assert state.attributes.get(ATTR_STATUS) is None

    await common.async_set_fan_speed(hass, FAN_SPEEDS[-1], entity_id=ENTITY_VACUUM_NONE)
    state = hass.states.get(ENTITY_VACUUM_NONE)
    assert state.attributes.get(ATTR_FAN_SPEED) != FAN_SPEEDS[-1]

    await common.async_clean_spot(hass, entity_id=ENTITY_VACUUM_BASIC)
    state = hass.states.get(ENTITY_VACUUM_BASIC)
    assert "spot" not in state.attributes.get(ATTR_STATUS)
    assert state.state == STATE_OFF

    # VacuumEntity should not support start and pause methods.
    hass.states.async_set(ENTITY_VACUUM_COMPLETE, STATE_ON)
    await hass.async_block_till_done()
    assert vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_pause(hass, ENTITY_VACUUM_COMPLETE)
    assert vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    hass.states.async_set(ENTITY_VACUUM_COMPLETE, STATE_OFF)
    await hass.async_block_till_done()
    assert not vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    await common.async_start(hass, ENTITY_VACUUM_COMPLETE)
    assert not vacuum.is_on(hass, ENTITY_VACUUM_COMPLETE)

    # StateVacuumEntity does not support on/off
    await common.async_turn_on(hass, entity_id=ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state != STATE_CLEANING

    await common.async_turn_off(hass, entity_id=ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state != STATE_RETURNING

    await common.async_toggle(hass, entity_id=ENTITY_VACUUM_STATE)
    state = hass.states.get(ENTITY_VACUUM_STATE)
    assert state.state != STATE_CLEANING


async def test_services(hass: HomeAssistant) -> None:
    """Test vacuum services."""
    # Test send_command
    send_command_calls = async_mock_service(hass, DOMAIN, SERVICE_SEND_COMMAND)

    params = {"rotate": 150, "speed": 20}
    await common.async_send_command(
        hass, "test_command", entity_id=ENTITY_VACUUM_BASIC, params=params
    )
    assert len(send_command_calls) == 1
    call = send_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_SEND_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_VACUUM_BASIC
    assert call.data[ATTR_COMMAND] == "test_command"
    assert call.data[ATTR_PARAMS] == params

    # Test set fan speed
    set_fan_speed_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_FAN_SPEED)

    await common.async_set_fan_speed(
        hass, FAN_SPEEDS[0], entity_id=ENTITY_VACUUM_COMPLETE
    )
    assert len(set_fan_speed_calls) == 1
    call = set_fan_speed_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_FAN_SPEED
    assert call.data[ATTR_ENTITY_ID] == ENTITY_VACUUM_COMPLETE
    assert call.data[ATTR_FAN_SPEED] == FAN_SPEEDS[0]


async def test_set_fan_speed(hass: HomeAssistant) -> None:
    """Test vacuum service to set the fan speed."""
    group_vacuums = ",".join(
        [ENTITY_VACUUM_BASIC, ENTITY_VACUUM_COMPLETE, ENTITY_VACUUM_STATE]
    )
    old_state_basic = hass.states.get(ENTITY_VACUUM_BASIC)
    old_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)
    old_state_state = hass.states.get(ENTITY_VACUUM_STATE)

    await common.async_set_fan_speed(hass, FAN_SPEEDS[0], entity_id=group_vacuums)

    new_state_basic = hass.states.get(ENTITY_VACUUM_BASIC)
    new_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)
    new_state_state = hass.states.get(ENTITY_VACUUM_STATE)

    assert old_state_basic == new_state_basic
    assert ATTR_FAN_SPEED not in new_state_basic.attributes

    assert old_state_complete != new_state_complete
    assert old_state_complete.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[1]
    assert new_state_complete.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[0]

    assert old_state_state != new_state_state
    assert old_state_state.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[1]
    assert new_state_state.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[0]


async def test_send_command(hass: HomeAssistant) -> None:
    """Test vacuum service to send a command."""
    group_vacuums = ",".join([ENTITY_VACUUM_BASIC, ENTITY_VACUUM_COMPLETE])
    old_state_basic = hass.states.get(ENTITY_VACUUM_BASIC)
    old_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)

    await common.async_send_command(
        hass, "test_command", params={"p1": 3}, entity_id=group_vacuums
    )

    new_state_basic = hass.states.get(ENTITY_VACUUM_BASIC)
    new_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)

    assert old_state_basic == new_state_basic
    assert old_state_complete != new_state_complete
    assert new_state_complete.state == STATE_ON
    assert (
        new_state_complete.attributes[ATTR_STATUS]
        == "Executing test_command({'p1': 3})"
    )
