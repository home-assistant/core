"""Tests for the System Bridge number platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.discord_control import DiscordAction, DiscordControl

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def number_only() -> Generator[None]:
    """Enable only the number platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.NUMBER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_number_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the number platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "value", "action"),
    [
        pytest.param(
            "number.hostname_discord_input_volume",
            50,
            DiscordAction.SET_INPUT_VOLUME,
            id="input_volume",
        ),
        pytest.param(
            "number.hostname_discord_output_volume",
            150,
            DiscordAction.SET_OUTPUT_VOLUME,
            id="output_volume",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_value(
    hass: HomeAssistant,
    mock_websocket_client: AsyncMock,
    entity_id: str,
    value: float,
    action: DiscordAction,
) -> None:
    """Test setting a volume sends the Discord control command."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_websocket_client.discord_control.assert_called_once_with(
        DiscordControl(action=action, value=value)
    )
