"""Fixtures for System Bridge integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Final
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from systembridgeconnector.const import EventKey, EventType
from systembridgemodels.fixtures.modules.battery import FIXTURE_BATTERY
from systembridgemodels.fixtures.modules.cpu import FIXTURE_CPU
from systembridgemodels.fixtures.modules.disks import FIXTURE_DISKS
from systembridgemodels.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgemodels.fixtures.modules.gpus import FIXTURE_GPUS
from systembridgemodels.fixtures.modules.media import FIXTURE_MEDIA
from systembridgemodels.fixtures.modules.memory import FIXTURE_MEMORY
from systembridgemodels.fixtures.modules.networks import FIXTURE_NETWORKS
from systembridgemodels.fixtures.modules.processes import FIXTURE_PROCESSES
from systembridgemodels.fixtures.modules.sensors import FIXTURE_SENSORS
from systembridgemodels.fixtures.modules.system import FIXTURE_SYSTEM
from systembridgemodels.media_directories import MediaDirectory
from systembridgemodels.media_files import MediaFile, MediaFiles
from systembridgemodels.modules import Module, ModulesData, RegisterDataListener
from systembridgemodels.response import Response

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import (
    FIXTURE_REQUEST_ID,
    FIXTURE_TITLE,
    FIXTURE_USER_INPUT,
    FIXTURE_UUID,
    mock_data_listener,
    setup_integration,
)

from tests.common import MockConfigEntry

REGISTER_MODULES: Final[list[Module]] = [
    Module.SYSTEM,
]


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


@pytest.fixture(autouse=True)
def mock_setup_notify_platform() -> Generator[AsyncMock]:
    """Mock notify platform setup."""
    with patch(
        "homeassistant.helpers.discovery.async_load_platform",
    ) as mock_setup_notify_platform:
        yield mock_setup_notify_platform


@pytest.fixture
def mock_version() -> Generator[AsyncMock]:
    """Return a mocked Version class."""
    with patch(
        "homeassistant.components.system_bridge.Version",
        autospec=True,
    ) as mock_version:
        version = mock_version.return_value
        version.check_supported.return_value = True

        yield version


@pytest.fixture
def mock_websocket_client(
    register_data_listener_model: RegisterDataListener = RegisterDataListener(
        modules=REGISTER_MODULES,
    ),
) -> Generator[MagicMock]:
    """Return a mocked WebSocketClient client."""

    with (
        patch(
            "homeassistant.components.system_bridge.coordinator.WebSocketClient",
            autospec=True,
        ) as mock_websocket_client,
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient",
            new=mock_websocket_client,
        ),
    ):
        websocket_client = mock_websocket_client.return_value
        websocket_client.connected = False
        websocket_client.get_data.return_value = ModulesData(
            battery=FIXTURE_BATTERY,
            cpu=FIXTURE_CPU,
            disks=FIXTURE_DISKS,
            displays=FIXTURE_DISPLAYS,
            gpus=FIXTURE_GPUS,
            media=FIXTURE_MEDIA,
            memory=FIXTURE_MEMORY,
            networks=FIXTURE_NETWORKS,
            processes=FIXTURE_PROCESSES,
            sensors=FIXTURE_SENSORS,
            system=FIXTURE_SYSTEM,
        )
        websocket_client.register_data_listener.return_value = Response(
            id=FIXTURE_REQUEST_ID,
            type=EventType.DATA_LISTENER_REGISTERED,
            message="Data listener registered",
            data={EventKey.MODULES: register_data_listener_model.modules},
        )
        # Trigger callback when listener is registered
        websocket_client.listen.side_effect = mock_data_listener

        websocket_client.get_directories.return_value = [
            MediaDirectory(
                key="documents",
                path="/home/user/documents",
            )
        ]
        websocket_client.get_files.return_value = MediaFiles(
            files=[
                MediaFile(
                    name="testsubdirectory",
                    path="testsubdirectory",
                    fullpath="/home/user/documents/testsubdirectory",
                    size=100,
                    last_accessed=1630000000,
                    created=1630000000,
                    modified=1630000000,
                    is_directory=True,
                    is_file=False,
                    is_link=False,
                ),
                MediaFile(
                    name="testfile.txt",
                    path="testfile.txt",
                    fullpath="/home/user/documents/testfile.txt",
                    size=100,
                    last_accessed=1630000000,
                    created=1630000000,
                    modified=1630000000,
                    is_directory=False,
                    is_file=True,
                    is_link=False,
                    mime_type="text/plain",
                ),
                MediaFile(
                    name="testfile.jpg",
                    path="testfile.jpg",
                    fullpath="/home/user/documents/testimage.jpg",
                    size=100,
                    last_accessed=1630000000,
                    created=1630000000,
                    modified=1630000000,
                    is_directory=False,
                    is_file=True,
                    is_link=False,
                    mime_type="image/jpeg",
                ),
            ],
            path="",
        )

        yield websocket_client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
) -> MockConfigEntry:
    """Initialize the System Bridge integration."""
    assert await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    return mock_config_entry
