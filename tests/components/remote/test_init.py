"""The tests for the Remote component, adapted from Light Test."""

from pytest_homeassistant.common import async_mock_service

from homeassistant.components import remote
from homeassistant.components.remote import DOMAIN, RemoteService, RemoteServiceArgument
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    TargetKey,
)
from homeassistant.core import HomeAssistant

TEST_PLATFORM = {DOMAIN: {CONF_PLATFORM: "test"}}
SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_DELETE_COMMAND = "delete_command"
ENTITY_ID = "entity_id_val"


async def test_is_on(hass: HomeAssistant) -> None:
    """Test is_on."""
    hass.states.async_set("remote.test", STATE_ON)
    assert remote.is_on(hass, "remote.test")

    hass.states.async_set("remote.test", STATE_OFF)
    assert not remote.is_on(hass, "remote.test")


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn_on."""
    turn_on_calls = async_mock_service(hass, DOMAIN, RemoteService.TURN_ON)
    await hass.services.async_call(
        DOMAIN, RemoteService.TURN_ON, {TargetKey.ENTITY_ID: ENTITY_ID}
    )

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    call = turn_on_calls[-1]

    assert call.domain == DOMAIN


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn_off."""
    turn_off_calls = async_mock_service(hass, DOMAIN, RemoteService.TURN_OFF)

    await hass.services.async_call(
        DOMAIN, RemoteService.TURN_OFF, {TargetKey.ENTITY_ID: ENTITY_ID}
    )

    await hass.async_block_till_done()

    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_send_command(hass: HomeAssistant) -> None:
    """Test send_command."""
    send_command_calls = async_mock_service(hass, DOMAIN, SERVICE_SEND_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        RemoteServiceArgument.DEVICE: "test_device",
        RemoteServiceArgument.COMMAND: ["test_command"],
        RemoteServiceArgument.NUM_REPEATS: "4",
        RemoteServiceArgument.DELAY_SECS: "0.6",
    }

    await hass.services.async_call(DOMAIN, SERVICE_SEND_COMMAND, data)

    await hass.async_block_till_done()

    assert len(send_command_calls) == 1
    call = send_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_SEND_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_learn_command(hass: HomeAssistant) -> None:
    """Test learn_command."""
    learn_command_calls = async_mock_service(hass, DOMAIN, SERVICE_LEARN_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        RemoteServiceArgument.DEVICE: "test_device",
        RemoteServiceArgument.COMMAND: ["test_command"],
        RemoteServiceArgument.COMMAND_TYPE: "rf",
        RemoteServiceArgument.ALTERNATIVE: True,
        RemoteServiceArgument.TIMEOUT: 20,
    }
    await hass.services.async_call(DOMAIN, SERVICE_LEARN_COMMAND, data)

    await hass.async_block_till_done()

    assert len(learn_command_calls) == 1
    call = learn_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_LEARN_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_delete_command(hass: HomeAssistant) -> None:
    """Test delete_command."""
    delete_command_calls = async_mock_service(
        hass, remote.DOMAIN, SERVICE_DELETE_COMMAND
    )

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        RemoteServiceArgument.DEVICE: "test_device",
        RemoteServiceArgument.COMMAND: ["test_command"],
    }

    await hass.services.async_call(DOMAIN, SERVICE_DELETE_COMMAND, data)

    await hass.async_block_till_done()

    assert len(delete_command_calls) == 1
    call = delete_command_calls[-1]

    assert call.domain == remote.DOMAIN
    assert call.service == SERVICE_DELETE_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID
