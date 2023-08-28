"""The tests for the SamsungTV remote platform."""
from unittest.mock import Mock

import pytest
from samsungtvws.encrypted.remote import SamsungTVEncryptedCommand

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_samsungtv_entry
from .test_media_player import MOCK_ENTRYDATA_ENCRYPTED_WS

ENTITY_ID = f"{REMOTE_DOMAIN}.fake"


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_setup(hass: HomeAssistant) -> None:
    """Test setup with basic config."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)
    assert hass.states.get(ENTITY_ID)


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique id."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    entity_registry = er.async_get(hass)

    main = entity_registry.async_get(ENTITY_ID)
    assert main.unique_id == "any"


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_main_services(
    hass: HomeAssistant, remoteencws: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for turn_off."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    remoteencws.send_commands.reset_mock()

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    # key called
    assert remoteencws.send_commands.call_count == 1
    commands = remoteencws.send_commands.call_args_list[0].args[0]
    assert len(commands) == 2
    assert isinstance(command := commands[0], SamsungTVEncryptedCommand)
    assert command.body["param3"] == "KEY_POWEROFF"
    assert isinstance(command := commands[1], SamsungTVEncryptedCommand)
    assert command.body["param3"] == "KEY_POWER"

    # commands not sent : power off in progress
    remoteencws.send_commands.reset_mock()
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["dash"]},
        blocking=True,
    )
    assert "TV is powering off, not sending keys: ['dash']" in caplog.text
    remoteencws.send_commands.assert_not_called()


@pytest.mark.usefixtures("remoteencws", "rest_api")
async def test_send_command_service(hass: HomeAssistant, remoteencws: Mock) -> None:
    """Test the send command."""
    await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["dash"]},
        blocking=True,
    )

    assert remoteencws.send_commands.call_count == 1
    commands = remoteencws.send_commands.call_args_list[0].args[0]
    assert len(commands) == 1
    assert isinstance(command := commands[0], SamsungTVEncryptedCommand)
    assert command.body["param3"] == "dash"
