"""The tests for the Demo vacuum platform."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.demo.vacuum import (
    DEMO_VACUUM_BASIC,
    DEMO_VACUUM_COMPLETE,
    DEMO_VACUUM_MINIMAL,
    DEMO_VACUUM_MOST,
    DEMO_VACUUM_NONE,
    FAN_SPEEDS,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_COMMAND,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_PARAMS,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    VacuumActivity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service
from tests.components.vacuum import common

ENTITY_VACUUM_BASIC = f"{VACUUM_DOMAIN}.{DEMO_VACUUM_BASIC}".lower()
ENTITY_VACUUM_COMPLETE = f"{VACUUM_DOMAIN}.{DEMO_VACUUM_COMPLETE}".lower()
ENTITY_VACUUM_MINIMAL = f"{VACUUM_DOMAIN}.{DEMO_VACUUM_MINIMAL}".lower()
ENTITY_VACUUM_MOST = f"{VACUUM_DOMAIN}.{DEMO_VACUUM_MOST}".lower()
ENTITY_VACUUM_NONE = f"{VACUUM_DOMAIN}.{DEMO_VACUUM_NONE}".lower()


@pytest.fixture
async def vacuum_only() -> None:
    """Enable only the datetime platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.VACUUM],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_vacuum(hass: HomeAssistant, vacuum_only: None):
    """Initialize setup demo vacuum."""
    assert await async_setup_component(
        hass, VACUUM_DOMAIN, {VACUUM_DOMAIN: {CONF_PLATFORM: "demo"}}
    )
    await hass.async_block_till_done()


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test vacuum supported features."""
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 16380
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) == "medium"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == FAN_SPEEDS
    assert state.state == VacuumActivity.DOCKED

    state = hass.states.get(ENTITY_VACUUM_MOST)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 12412
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) == "medium"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == FAN_SPEEDS
    assert state.state == VacuumActivity.DOCKED

    state = hass.states.get(ENTITY_VACUUM_BASIC)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 12360
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == VacuumActivity.DOCKED

    state = hass.states.get(ENTITY_VACUUM_MINIMAL)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == VacuumActivity.DOCKED

    state = hass.states.get(ENTITY_VACUUM_NONE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.state == VacuumActivity.DOCKED


async def test_methods(hass: HomeAssistant) -> None:
    """Test if methods call the services as expected."""
    await common.async_start(hass, ENTITY_VACUUM_BASIC)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_BASIC)
    assert state.state == VacuumActivity.CLEANING

    await common.async_stop(hass, ENTITY_VACUUM_BASIC)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_BASIC)
    assert state.state == VacuumActivity.IDLE

    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    await hass.async_block_till_done()
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 100
    assert state.state == VacuumActivity.DOCKED

    await async_setup_component(hass, "notify", {})
    await hass.async_block_till_done()
    await common.async_locate(hass, ENTITY_VACUUM_COMPLETE)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.IDLE

    await common.async_return_to_base(hass, ENTITY_VACUUM_COMPLETE)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.RETURNING

    await common.async_set_fan_speed(
        hass, FAN_SPEEDS[-1], entity_id=ENTITY_VACUUM_COMPLETE
    )
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.attributes.get(ATTR_FAN_SPEED) == FAN_SPEEDS[-1]

    await common.async_clean_spot(hass, ENTITY_VACUUM_COMPLETE)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.CLEANING

    await common.async_pause(hass, ENTITY_VACUUM_COMPLETE)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.PAUSED

    await common.async_return_to_base(hass, ENTITY_VACUUM_COMPLETE)
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.RETURNING

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_VACUUM_COMPLETE)
    assert state.state == VacuumActivity.DOCKED


async def test_unsupported_methods(hass: HomeAssistant) -> None:
    """Test service calls for unsupported vacuums."""

    with pytest.raises(HomeAssistantError):
        await common.async_stop(hass, ENTITY_VACUUM_NONE)

    with pytest.raises(HomeAssistantError):
        await common.async_locate(hass, ENTITY_VACUUM_NONE)

    with pytest.raises(HomeAssistantError):
        await common.async_return_to_base(hass, ENTITY_VACUUM_NONE)

    with pytest.raises(HomeAssistantError):
        await common.async_set_fan_speed(
            hass, FAN_SPEEDS[-1], entity_id=ENTITY_VACUUM_NONE
        )
    with pytest.raises(HomeAssistantError):
        await common.async_clean_spot(hass, ENTITY_VACUUM_NONE)

    with pytest.raises(HomeAssistantError):
        await common.async_pause(hass, ENTITY_VACUUM_NONE)

    with pytest.raises(HomeAssistantError):
        await common.async_start(hass, ENTITY_VACUUM_NONE)


async def test_services(hass: HomeAssistant) -> None:
    """Test vacuum services."""
    # Test send_command
    send_command_calls = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_SEND_COMMAND)

    params = {"rotate": 150, "speed": 20}
    await common.async_send_command(
        hass, "test_command", entity_id=ENTITY_VACUUM_BASIC, params=params
    )
    assert len(send_command_calls) == 1
    call = send_command_calls[-1]

    assert call.domain == VACUUM_DOMAIN
    assert call.service == SERVICE_SEND_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_VACUUM_BASIC
    assert call.data[ATTR_COMMAND] == "test_command"
    assert call.data[ATTR_PARAMS] == params

    # Test set fan speed
    set_fan_speed_calls = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_SET_FAN_SPEED)

    await common.async_set_fan_speed(hass, FAN_SPEEDS[0], ENTITY_VACUUM_COMPLETE)
    assert len(set_fan_speed_calls) == 1
    call = set_fan_speed_calls[-1]

    assert call.domain == VACUUM_DOMAIN
    assert call.service == SERVICE_SET_FAN_SPEED
    assert call.data[ATTR_ENTITY_ID] == ENTITY_VACUUM_COMPLETE
    assert call.data[ATTR_FAN_SPEED] == FAN_SPEEDS[0]


async def test_set_fan_speed(hass: HomeAssistant) -> None:
    """Test vacuum service to set the fan speed."""
    group_vacuums = f"{ENTITY_VACUUM_COMPLETE},{ENTITY_VACUUM_MOST}"
    old_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)
    old_state_most = hass.states.get(ENTITY_VACUUM_MOST)

    await common.async_set_fan_speed(hass, FAN_SPEEDS[0], entity_id=group_vacuums)

    new_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)
    new_state_most = hass.states.get(ENTITY_VACUUM_MOST)

    assert old_state_complete != new_state_complete
    assert old_state_complete.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[1]
    assert new_state_complete.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[0]

    assert old_state_most != new_state_most
    assert old_state_most.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[1]
    assert new_state_most.attributes[ATTR_FAN_SPEED] == FAN_SPEEDS[0]


async def test_send_command(hass: HomeAssistant) -> None:
    """Test vacuum service to send a command."""
    group_vacuums = f"{ENTITY_VACUUM_COMPLETE}"
    old_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)

    await common.async_send_command(
        hass, "test_command", params={"p1": 3}, entity_id=group_vacuums
    )

    new_state_complete = hass.states.get(ENTITY_VACUUM_COMPLETE)

    assert old_state_complete != new_state_complete
    assert new_state_complete.state == VacuumActivity.IDLE
