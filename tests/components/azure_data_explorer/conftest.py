"""Test fixtures for ADX."""
from dataclasses import dataclass
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest

from homeassistant.components.azure_data_explorer.const import (
    CONF_FILTER,
    CONF_SEND_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import AZURE_DATA_EXPLORER_PATH, BASE_CONFIG, BASIC_OPTIONS, CLIENT_PATH

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


# fixtures for both init and config flow tests
@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    entity_id: str
    expected_count: int


@pytest.fixture(name="filter_schema")
def mock_filter_schema():
    """Return an empty filter."""
    return {}


@pytest.fixture(autouse=False, name="mock_azure_data_explorer_test_connection")
def mock_azure_data_explorer_test_connection():
    """Mock azure data explorer test_connection, used to test the connection."""
    with patch(
        f"{CLIENT_PATH}.test_connection", return_value=None
    ) as AzureDataExplorer_test_connection:
        yield AzureDataExplorer_test_connection


@pytest.fixture(autouse=False, name="mock_test_connection")
def mock_test_connection():
    """Mock azure data explorer client test_connection, used to test the connection."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.AzureDataExplorerClient.test_connection",
        return_value=None,
    ) as test_connection:
        yield test_connection


@pytest.fixture(autouse=False, name="mock_azure_data_explorer_client_ingest_data")
def mock_azure_data_explorer_client_ingest_data():
    """Mock azure data explorer client_ingest_data."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.AzureDataExplorerClient.ingest_data",
        return_value=None,
    ) as ingest_data:
        yield ingest_data


@pytest.fixture(autouse=False, name="mock_validate_input")
def mock_validate_input():
    """Mock validate_input ."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.config_flow.ConfigFlow.validate_input",
        return_value=None,
    ) as ingestionResult:
        yield ingestionResult


@pytest.fixture(name="entry")
async def mock_entry_fixture(hass, filter_schema):
    """Create the setup in HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=BASE_CONFIG,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
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
    return entry


# fixtures for init tests
@pytest.fixture(name="entry_with_one_event")
async def mock_entry_with_one_event(hass, entry):
    """Use the entry and add a single test event to the queue."""
    assert entry.state == ConfigEntryState.LOADED
    hass.states.async_set("sensor.test", STATE_ON)
    return entry


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry():
    """Mock the setup entry call, used for config flow tests."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


# Fixtures for client tests
@pytest.fixture(autouse=True, name="mock_managed_streaming")
def mock_managed_streaming():
    """Mock ManagedStreamingIngestClient ingest_from_stream."""
    with patch(
        "azure.kusto.ingest.ManagedStreamingIngestClient.ingest_from_stream",
        return_value=True,
    ) as ingestionResult:
        yield ingestionResult


@pytest.fixture(autouse=True, name="mock_queued")
def mock_queued():
    """Mock QueuedIngestClient ingest_from_stream."""
    with patch(
        "azure.kusto.ingest.QueuedIngestClient.ingest_from_stream",
        return_value=True,
    ) as ingestionResult:
        yield ingestionResult


@pytest.fixture(autouse=True, name="mock_execute_query")
def mock_execute_query():
    """Mock KustoClient execute_query."""
    with patch(
        "azure.kusto.data.KustoClient.execute_query",
        return_value=True,
    ) as KustoResponseDataSet:
        yield KustoResponseDataSet
