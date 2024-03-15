"""Fixtures for System Bridge integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from systembridgeconnector.const import (
    EVENT_MODULES,
    TYPE_DATA_GET,
    TYPE_DATA_LISTENER_REGISTERED,
)
from systembridgemodels.modules import GetData, RegisterDataListener
from systembridgemodels.response import Response

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import FIXTURE_REQUEST_ID, FIXTURE_TITLE, FIXTURE_USER_INPUT, FIXTURE_UUID

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title=FIXTURE_TITLE,
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=SystemBridgeConfigFlow.MINOR_VERSION,
        data={
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
            CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Let some time pass so coordinators can be reliably triggered by bumping
    # time by SCAN_INTERVAL
    freezer.tick(1)

    return mock_config_entry


@pytest.fixture
def mock_websocket_client(
    get_data_model: GetData = GetData(
        modules=["system"],
    ),
    register_data_listener_model: RegisterDataListener = RegisterDataListener(
        modules=["system"]
    ),
) -> Generator[MagicMock, None, None]:
    """Return a mocked WebSocketClient."""
    with patch(
        "homeassistant.components.system_bridge.coordinator.WebSocketClient",
        autospec=True,
    ) as mock_websocket_client, patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient",
        new=mock_websocket_client,
    ):
        websocket_client = mock_websocket_client.return_value
        websocket_client.connected = False
        websocket_client.get_data.return_value = Response(
            id=FIXTURE_REQUEST_ID,
            type=TYPE_DATA_GET,
            message="Getting data",
            data={EVENT_MODULES: get_data_model.modules},
        )
        websocket_client.register_data_listener.return_value = Response(
            id=FIXTURE_REQUEST_ID,
            type=TYPE_DATA_LISTENER_REGISTERED,
            message="Data listener registered",
            data={EVENT_MODULES: register_data_listener_model.modules},
        )

        yield websocket_client
