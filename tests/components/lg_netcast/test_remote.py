"""Tests for LG Netcast remote platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pylgnetcast import LG_COMMAND
import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
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
    """Test remote.send_command raises ServiceValidationError  for an unknown command name."""
    await setup_lgnetcast(hass)

    with pytest.raises(ServiceValidationError, match="Unknown command"):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: REMOTE_ENTITY_ID, ATTR_COMMAND: ["NOT_A_REAL_COMMAND"]},
            blocking=True,
        )
