"""Test the init functions for AEH."""
import logging

from homeassistant.components import azure_data_explorer
from homeassistant.components.azure_data_explorer.client import AzureDataExplorerClient

from .const import BASE_CONFIG_FULL, BASIC_OPTIONS

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_managedstreaming_ingestion(mock_managed_streaming):
    """Test ManagedStreaming ingestion."""

    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    client = AzureDataExplorerClient(
        clusteringesturi=entry.data["clusteringesturi"],
        database=entry.data["database"],
        table=entry.data["table"],
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
        authority_id=entry.data["authority_id"],
        use_free_cluster=False,
    )

    adx_events = '{"this_is": "Valid_JSON"}'

    client.ingest_data(adx_events)

    mock_managed_streaming.assert_called_once()


async def test_queued_ingestion(mock_queued):
    """Test ManagedStreaming ingestion."""

    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    client = AzureDataExplorerClient(
        clusteringesturi=entry.data["clusteringesturi"],
        database=entry.data["database"],
        table=entry.data["table"],
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
        authority_id=entry.data["authority_id"],
        use_free_cluster=True,
    )

    adx_events = '{"this_is": "Valid_JSON"}'

    client.ingest_data(adx_events)

    mock_queued.assert_called_once()


async def test_test_connection(mock_execute_query):
    """Test test_connection."""

    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    client = AzureDataExplorerClient(
        clusteringesturi=entry.data["clusteringesturi"],
        database=entry.data["database"],
        table=entry.data["table"],
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
        authority_id=entry.data["authority_id"],
        use_free_cluster=True,
    )

    client.test_connection()

    mock_execute_query.assert_called_once()
