"""Tests for LG Netcast remote platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, call, patch

from pylgnetcast import LG_COMMAND
import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import MODEL_NAME, setup_lgnetcast

REMOTE_ENTITY_ID = f"{REMOTE_DOMAIN}.{MODEL_NAME.lower()}"


@pytest.fixture(autouse=True)
def mock_lg_netcast() -> Generator[MagicMock]:
    """Mock LG Netcast library."""
    with patch(
        "homeassistant.components.lg_netcast.LgNetCastClient"
    ) as mock_client_class:
        yield mock_client_class


async def test_send_command(hass: HomeAssistant, mock_lg_netcast: MagicMock) -> None:
    """Test remote.send_command calls the client with the correct command code."""
    await setup_lgnetcast(hass)
    context_client = mock_lg_netcast.return_value.__enter__.return_value

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: REMOTE_ENTITY_ID, ATTR_COMMAND: ["POWER"]},
        blocking=True,
    )

    context_client.send_command.assert_called_once_with(LG_COMMAND.POWER)


async def test_send_command_invalid(
    hass: HomeAssistant, mock_lg_netcast: MagicMock
) -> None:
    """Test send_command raises error for unknown command name."""
    await setup_lgnetcast(hass)

    with pytest.raises(ServiceValidationError, match="Unknown command"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: REMOTE_ENTITY_ID, ATTR_COMMAND: ["NOT_A_REAL_COMMAND"]},
            blocking=True,
        )


async def test_send_multiple_commands(
    hass: HomeAssistant, mock_lg_netcast: MagicMock
) -> None:
    """Test remote.send_command calls the client for each command in the list."""
    await setup_lgnetcast(hass)
    context_client = mock_lg_netcast.return_value.__enter__.return_value

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: REMOTE_ENTITY_ID, ATTR_COMMAND: ["POWER", "NUMBER_0"]},
        blocking=True,
    )

    assert context_client.send_command.call_count == 2
    context_client.send_command.assert_has_calls(
        [
            call(LG_COMMAND.POWER),
            call(LG_COMMAND.NUMBER_0),
        ]
    )


async def test_send_multiple_commands_with_delay(
    hass: HomeAssistant, mock_lg_netcast: MagicMock
) -> None:
    """Test remote.send_command sleeps between commands when delay_secs is set."""
    await setup_lgnetcast(hass)
    context_client = mock_lg_netcast.return_value.__enter__.return_value

    with patch("homeassistant.components.lg_netcast.remote.time.sleep") as mock_sleep:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["POWER", "NUMBER_0", "NUMBER_1"],
                ATTR_DELAY_SECS: 0.5,
            },
            blocking=True,
        )

    assert context_client.send_command.call_count == 3
    context_client.send_command.assert_has_calls(
        [
            call(LG_COMMAND.POWER),
            call(LG_COMMAND.NUMBER_0),
            call(LG_COMMAND.NUMBER_1),
        ]
    )
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(0.5)


async def test_send_command_repeats_with_delay(
    hass: HomeAssistant, mock_lg_netcast: MagicMock
) -> None:
    """Test remote.send_command sleeps between repeats when delay_secs is set."""
    await setup_lgnetcast(hass)
    context_client = mock_lg_netcast.return_value.__enter__.return_value

    with patch("homeassistant.components.lg_netcast.remote.time.sleep") as mock_sleep:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["POWER"],
                ATTR_NUM_REPEATS: 3,
                ATTR_DELAY_SECS: 0.5,
            },
            blocking=True,
        )

    assert context_client.send_command.call_count == 3
    # sleep once before each repeat after the first (2 times), no sleep between commands since there's only one
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(0.5)


async def test_send_multiple_commands_repeats_with_delay(
    hass: HomeAssistant, mock_lg_netcast: MagicMock
) -> None:
    """Test remote.send_command sleeps between commands and between repeats."""
    await setup_lgnetcast(hass)
    context_client = mock_lg_netcast.return_value.__enter__.return_value

    with patch("homeassistant.components.lg_netcast.remote.time.sleep") as mock_sleep:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
                ATTR_COMMAND: ["POWER", "NUMBER_0"],
                ATTR_NUM_REPEATS: 3,
                ATTR_DELAY_SECS: 0.5,
            },
            blocking=True,
        )

    # 2 commands x 3 repeats = 6 total sends
    assert context_client.send_command.call_count == 6
    # 1 sleep between the 2 commands per repeat (3 repeats) + 1 sleep before each repeat after the first (2)
    # = 3 + 2 = 5 sleeps total
    assert mock_sleep.call_count == 5
    mock_sleep.assert_called_with(0.5)
