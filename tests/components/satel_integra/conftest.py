"""Satel Integra tests configuration."""

from collections.abc import Generator
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.satel_integra.const import DOMAIN

from . import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
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
def mock_satel() -> Generator[AsyncMock]:
    """Override the satel test."""
    with (
        patch(
            "homeassistant.components.satel_integra.AsyncSatel",
            autospec=True,
        ) as client,
        patch(
            "homeassistant.components.satel_integra.config_flow.AsyncSatel", new=client
        ),
    ):
        client.return_value.partition_states = {}
        client.return_value.violated_outputs = []
        client.return_value.violated_zones = []
        client.return_value.connect.return_value = True

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock satel configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.2",
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
        entry_id="SATEL_INTEGRA_CONFIG_ENTRY_1",
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_config_entry_with_subentries(
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Mock satel configuration entry."""
    mock_config_entry.subentries = MappingProxyType(
        {
            MOCK_PARTITION_SUBENTRY.subentry_id: MOCK_PARTITION_SUBENTRY,
            MOCK_ZONE_SUBENTRY.subentry_id: MOCK_ZONE_SUBENTRY,
            MOCK_OUTPUT_SUBENTRY.subentry_id: MOCK_OUTPUT_SUBENTRY,
            MOCK_SWITCHABLE_OUTPUT_SUBENTRY.subentry_id: MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
        }
    )
    return mock_config_entry
