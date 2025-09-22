"""Fixtures for Rejseplanen tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData

from tests.common import MockConfigEntry, patch


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rejseplanen.async_setup_entry", return_value=True
    ):
        yield mock_setup_entry


@pytest.fixture
def mock_rejseplan() -> Generator[AsyncMock]:
    """Mock Rejseplanen."""

    with (
        patch(
            "homeassistant.components.rejseplanen.RejseplanenDataUpdateCoordinator",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Rejseplanen configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="rejseplanen",
        data={
            CONF_NAME: "Rejseplanen",
            CONF_API_KEY: "token",
        },
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_STOP_ID: "123456",
                    CONF_NAME: "mytopic",
                    CONF_ROUTE: "myroute",
                    CONF_DIRECTION: "mydirection",
                    CONF_DEPARTURE_TYPE: "departure",
                },
                subentry_id="ABCDEF",
                subentry_type="topic",
                title="mytopic",
                unique_id="mytopic",
            )
        ],
    )
