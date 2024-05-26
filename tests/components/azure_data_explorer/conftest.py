"""Test fixtures for Azure Data Explorer."""

from collections.abc import Generator
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.azure_data_explorer.const import (
    CONF_FILTER,
    CONF_SEND_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import (
    AZURE_DATA_EXPLORER_PATH,
    BASE_CONFIG_FREE,
    BASE_CONFIG_FULL,
    BASIC_OPTIONS,
)

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(name="filter_schema")
def mock_filter_schema() -> dict[str, Any]:
    """Return an empty filter."""
    return {}


@pytest.fixture(name="entry_managed")
async def mock_entry_fixture_managed(
    hass: HomeAssistant, filter_schema: dict[str, Any]
) -> MockConfigEntry:
    """Create the setup in HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    await _entry(hass, filter_schema, entry)
    return entry


@pytest.fixture(name="entry_queued")
async def mock_entry_fixture_queued(
    hass: HomeAssistant, filter_schema: dict[str, Any]
) -> MockConfigEntry:
    """Create the setup in HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_CONFIG_FREE,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    await _entry(hass, filter_schema, entry)
    return entry


async def _entry(hass: HomeAssistant, filter_schema: dict[str, Any], entry) -> None:
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_FILTER: filter_schema}}
    )
    assert entry.state == ConfigEntryState.LOADED

    # Clear the component_loaded event from the queue.
    async_fire_time_changed(
        hass,
        utcnow() + timedelta(seconds=entry.options[CONF_SEND_INTERVAL]),
    )
    await hass.async_block_till_done()


@pytest.fixture(name="entry_with_one_event")
async def mock_entry_with_one_event(
    hass: HomeAssistant, entry_managed
) -> MockConfigEntry:
    """Use the entry and add a single test event to the queue."""
    assert entry_managed.state == ConfigEntryState.LOADED
    hass.states.async_set("sensor.test", STATE_ON)
    return entry_managed


# Fixtures for config_flow tests
@pytest.fixture
def mock_setup_entry() -> Generator[MockConfigEntry, None, None]:
    """Mock the setup entry call, used for config flow tests."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


# Fixtures for mocking the Azure Data Explorer SDK calls.
@pytest.fixture(autouse=True)
def mock_managed_streaming() -> Generator[mock_entry_fixture_managed, Any, Any]:
    """mock_azure_data_explorer_ManagedStreamingIngestClient_ingest_data."""
    with patch(
        "azure.kusto.ingest.ManagedStreamingIngestClient.ingest_from_stream",
        return_value=True,
    ) as ingest_from_stream:
        yield ingest_from_stream


@pytest.fixture(autouse=True)
def mock_queued_ingest() -> Generator[mock_entry_fixture_queued, Any, Any]:
    """mock_azure_data_explorer_QueuedIngestClient_ingest_data."""
    with patch(
        "azure.kusto.ingest.QueuedIngestClient.ingest_from_stream",
        return_value=True,
    ) as ingest_from_stream:
        yield ingest_from_stream


@pytest.fixture(autouse=True)
def mock_execute_query() -> Generator[Mock, Any, Any]:
    """Mock KustoClient execute_query."""
    with patch(
        "azure.kusto.data.KustoClient.execute_query",
        return_value=True,
    ) as execute_query:
        yield execute_query
