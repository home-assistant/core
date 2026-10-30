"""Tests for the System Bridge button platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.response import Response

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_REQUEST_ID

SHUTDOWN_ENTITY_ID = "button.hostname_shut_down"


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_button_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the button platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        pytest.param("button.hostname_sleep", "power_sleep", id="sleep"),
        pytest.param("button.hostname_hibernate", "power_hibernate", id="hibernate"),
        pytest.param("button.hostname_restart", "power_restart", id="restart"),
        pytest.param(SHUTDOWN_ENTITY_ID, "power_shutdown", id="shutdown"),
        pytest.param("button.hostname_lock", "power_lock", id="lock"),
        pytest.param("button.hostname_log_out", "power_logout", id="logout"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_button(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test pressing a power button sends its power command."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_websocket_client, method).assert_awaited_once_with()


@pytest.mark.parametrize(
    ("side_effect", "match"),
    [
        pytest.param(
            [
                Response(
                    id=FIXTURE_REQUEST_ID,
                    type=EventType.ERROR,
                    message="Shutdown is not supported",
                    data={},
                )
            ],
            "Failed to send the power command: Shutdown is not supported",
            id="error_response",
        ),
        pytest.param(
            ConnectionClosedException("Connection is closed"),
            "A connection error occurred",
            id="connection_closed",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_button_failure(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    side_effect: list[Response] | Exception,
    match: str,
) -> None:
    """Test a failed power command raises."""
    mock_websocket_client.power_shutdown.side_effect = side_effect

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: SHUTDOWN_ENTITY_ID},
            blocking=True,
        )
