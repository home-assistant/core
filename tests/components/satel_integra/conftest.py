"""Satel Integra tests configuration."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.satel_integra.const import DOMAIN

from . import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_ENTRY_ID,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
    get_monitor_callbacks,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.satel_integra.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def patch_debounce() -> Generator[None]:
    """Override coordinator debounce time."""
    with patch(
        "homeassistant.components.satel_integra.coordinator.PARTITION_UPDATE_DEBOUNCE_DELAY",
        0,
    ):
        yield


@pytest.fixture
def mock_satel() -> Generator[AsyncMock]:
    """Override the satel test."""
    with (
        patch(
            "homeassistant.components.satel_integra.client.AsyncSatel",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.satel_integra.config_flow.AsyncSatel",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        client.partition_states = {}
        client.violated_outputs = []
        client.violated_zones = []

        client.connect = AsyncMock(return_value=True)
        client.set_output = AsyncMock()

        client.register_callbacks = MagicMock()

        # Immediately push baseline values so entities have stable states for snapshots
        async def _start(**_: object) -> None:
            alarm_status_callback, zone_changed_callback, output_changed_callback = (
                get_monitor_callbacks(client)
            )
            alarm_status_callback()
            zone_changed_callback({1: 0})
            output_changed_callback({1: 0})

        client.start = AsyncMock(side_effect=_start)

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock satel configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
        version=2,
        minor_version=1,
    )


@pytest.fixture
def mock_config_entry_with_subentries(
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Mock satel configuration entry."""
    mock_config_entry.subentries = deepcopy(
        {
            MOCK_PARTITION_SUBENTRY.subentry_id: MOCK_PARTITION_SUBENTRY,
            MOCK_ZONE_SUBENTRY.subentry_id: MOCK_ZONE_SUBENTRY,
            MOCK_OUTPUT_SUBENTRY.subentry_id: MOCK_OUTPUT_SUBENTRY,
            MOCK_SWITCHABLE_OUTPUT_SUBENTRY.subentry_id: MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
        }
    )
    return mock_config_entry


@pytest.fixture
def mock_reload_after_entry_update() -> Generator[MagicMock]:
    """Mock out the reload after updating the entry."""
    with patch("homeassistant.components.satel_integra.update_listener") as mock_reload:
        yield mock_reload
