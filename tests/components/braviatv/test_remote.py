"""Test the Bravia TV remote."""

from typing import Any
from unittest.mock import AsyncMock, call, patch

from pybravia import BraviaError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration

ENTITY_ID = "remote.bravia_tv_model"


@pytest.mark.usefixtures("mock_braviatv_client")
async def test_remote(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the remote."""
    with patch("homeassistant.components.braviatv.PLATFORMS", [Platform.REMOTE]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_remote_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test the remote is off when the TV is in standby."""
    mock_braviatv_client.get_power_status.return_value = "standby"

    await init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    service: str,
    method: str,
) -> None:
    """Test turning the TV on and off."""
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        REMOTE_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(mock_braviatv_client, method).assert_called_once()


@pytest.mark.parametrize(
    ("extra_data", "expected_calls"),
    [
        ({}, [call("Power"), call("Num1")]),
        (
            {ATTR_NUM_REPEATS: 2},
            [call("Power"), call("Num1"), call("Power"), call("Num1")],
        ),
    ],
)
async def test_send_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    extra_data: dict[str, Any],
    expected_calls: list[Any],
) -> None:
    """Test sending commands."""
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["Power", "Num1"], **extra_data},
        blocking=True,
    )

    assert mock_braviatv_client.send_command.call_args_list == expected_calls


async def test_send_command_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test sending a command not supported by the TV."""
    await init_integration(hass, mock_config_entry)

    mock_braviatv_client.send_command.return_value = False

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_COMMAND: ["Foo", "Bar"],
                ATTR_NUM_REPEATS: 2,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "unsupported_command"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "command": "Foo",
    }
    mock_braviatv_client.send_command.assert_called_once_with("Foo")


async def test_send_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test error while sending commands."""
    await init_integration(hass, mock_config_entry)

    mock_braviatv_client.send_command.side_effect = BraviaError

    with pytest.raises(
        HomeAssistantError, match="Error sending command to BRAVIA TV-Model"
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["Power"]},
            blocking=True,
        )
