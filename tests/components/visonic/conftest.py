"""Common fixtures for the Visonic integration."""

import asyncio
from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from homeassistant.components.visonic.cloud import VisonicCloudConnection
from homeassistant.components.visonic.connection_test import ConnectionTest
from homeassistant.components.visonic.coordinator import VisonicCoordinator
from homeassistant.components.visonic.direct import VisonicDirectConnection
from homeassistant.components.visonic.visonic_data_types import (
    VisonicConfigEntry,
    VisonicCoordinatorData,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .helpers import create_mock_config_entry


@pytest.fixture
def mock_connection_test():
    """Prevent network validation and expose one registered cloud panel."""
    original_init = ConnectionTest.__init__

    def initialize(self: ConnectionTest) -> None:
        original_init(self)
        self.panels = {"ABCDEF": "Home (ABCDEF)"}

    with (
        patch.object(ConnectionTest, "__init__", initialize),
        patch.object(
            ConnectionTest, "test_connection", new=AsyncMock(return_value=None)
        ) as mock,
    ):
        yield mock


@pytest.fixture
def mock_panel_connect_result():
    """Prevent a real panel connection."""

    with (
        patch.object(
            VisonicDirectConnection,
            "create_state_snapshot",
            AsyncMock(return_value=VisonicCoordinatorData(connected=True)),
        ),
        patch.object(
            VisonicCloudConnection,
            "create_state_snapshot",
            AsyncMock(return_value=VisonicCoordinatorData(connected=True)),
        ),
        patch.object(
            VisonicDirectConnection,
            "async_panel_connect",
            AsyncMock(return_value=True),
        ) as direct_connect,
        patch.object(
            VisonicCloudConnection,
            "async_panel_connect",
            AsyncMock(return_value=True),
        ) as cloud_connect,
    ):
        yield direct_connect, cloud_connect


@pytest.fixture
def mock_panel_connect():
    """Prevent a real panel connection using ethernet or serial."""
    with (
        patch.object(
            VisonicDirectConnection,
            "async_panel_connect",
            AsyncMock(return_value=True),
        ),
        patch.object(
            VisonicCloudConnection,
            "async_panel_connect",
            AsyncMock(return_value=True),
        ),
    ):
        yield


@pytest.fixture
def mock_forward_entry_setups():
    """Prevent loading real platforms."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        new=AsyncMock(return_value=True),
    ) as forward:
        yield forward


@pytest_asyncio.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_connection_test,
    mock_panel_connect,
    mock_forward_entry_setups,
):
    """Return a function that sets up the integration."""
    entries = []

    async def _setup(
        *,
        data: dict | None = None,
        options: dict | None = None,
    ) -> tuple[bool, VisonicConfigEntry]:
        entry = create_mock_config_entry(data=data, options=options)
        entry.add_to_hass(hass)
        with (
            patch.object(
                VisonicDirectConnection,
                "create_state_snapshot",
                AsyncMock(return_value=VisonicCoordinatorData(connected=True)),
            ),
            patch.object(
                VisonicCloudConnection,
                "create_state_snapshot",
                AsyncMock(return_value=VisonicCoordinatorData(connected=True)),
            ),
        ):
            result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entries.append(entry)
        return result, cast(VisonicConfigEntry, entry)

    yield _setup

    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            with patch.object(
                hass.config_entries,
                "async_unload_platforms",
                AsyncMock(return_value=True),
            ):
                await hass.config_entries.async_unload(entry.entry_id)
        elif entry.state is ConfigEntryState.FAILED_UNLOAD:
            await entry.runtime_data.coordinator.async_panel_stop()
            await entry.runtime_data.coordinator.async_shutdown()
    await hass.async_block_till_done()


@pytest_asyncio.fixture
async def setup_integration_with_connection(
    hass: HomeAssistant,
    mock_connection_test,
    mock_forward_entry_setups,
):
    """Return a function that sets up the integration."""
    entries = []

    async def _setup(
        *,
        data: dict | None = None,
        options: dict | None = None,
    ) -> tuple[bool, VisonicConfigEntry]:
        entry = create_mock_config_entry(data=data, options=options)
        entry.add_to_hass(hass)
        with (
            patch.object(
                VisonicCloudConnection,
                "create_state_snapshot",
                AsyncMock(return_value=VisonicCoordinatorData(connected=True)),
            ),
            patch.object(
                VisonicCloudConnection,
                "async_panel_connect",
                AsyncMock(return_value=True),
            ),
        ):
            result = await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            entries.append(entry)
            return result, cast(VisonicConfigEntry, entry)

    yield _setup

    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            with patch.object(
                hass.config_entries,
                "async_unload_platforms",
                AsyncMock(return_value=True),
            ):
                await hass.config_entries.async_unload(entry.entry_id)
        elif entry.state is ConfigEntryState.FAILED_UNLOAD:
            await entry.runtime_data.coordinator.async_panel_stop()
            await entry.runtime_data.coordinator.async_shutdown()
    await hass.async_block_till_done()


@pytest_asyncio.fixture
async def wait_for_coordinator_timer():
    """Wait for coordinator timer for the update timeout."""
    callback_called = asyncio.Event()

    @callback
    def timer_callback(self, _now: datetime) -> None:
        callback_called.set()

    with patch.object(
        VisonicCoordinator,
        "_coordinator_update_timer_callback",
        new=timer_callback,
    ):

        async def wait() -> None:
            await asyncio.wait_for(
                callback_called.wait(),
                timeout=1.0,
            )

        yield wait
