"""Setting up the ingest client."""
from __future__ import annotations

import io
import logging

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import (
    IngestionProperties,
    ManagedStreamingIngestClient,
    QueuedIngestClient,
    StreamDescriptor,
)

_LOGGER = logging.getLogger(__name__)

# Suppress very verbose logging from client
logger = logging.getLogger("azure")
logger.setLevel(logging.WARNING)


class AzureDataExplorerClient:
    """Class for Azure Data Explorer Client."""

    def __init__(self, **data) -> None:
        """Create the right class."""

        self.cluster_ingest_uri = data["cluster_ingest_uri"]
        self.database = data["database"]
        self.table = data["table"]
        self.client_id = data["client_id"]
        self.client_secret = data["client_secret"]
        self.authority_id = data["authority_id"]
        self.use_queued_ingestion = data["use_queued_ingestion"]

        self.cluster_query_uri = self.cluster_ingest_uri.replace(
            "https://ingest-", "https://"
        )

        self.ingestion_properties = IngestionProperties(
            database=self.database,
            table=self.table,
            data_format=DataFormat.MULTIJSON,
            ingestion_mapping_reference="ha_json_mapping",
        )

        # Create cLients for ingesting and querying data
        kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(
            self.cluster_ingest_uri,
            self.client_id,
            self.client_secret,
            self.authority_id,
        )

        if self.use_queued_ingestion is True:
            # Queded is the only option supported on free tear of ADX
            self.write_client = QueuedIngestClient(kcsb)
        else:
            self.write_client = ManagedStreamingIngestClient.from_dm_kcsb(kcsb)

        self.query_client = KustoClient(kcsb)

    def test_connection(self) -> None:
        """Test connection, will throw Exception when it cannot connect."""

        query = f"{self.table} | take 1"

        self.query_client.execute_query(self.database, query)

    def ingest_data(self, adx_events: str) -> None:
        """Send data to Axure Data Explorer."""

        bytes_stream = io.StringIO(adx_events)
        stream_descriptor = StreamDescriptor(bytes_stream)

        self.write_client.ingest_from_stream(
            stream_descriptor, ingestion_properties=self.ingestion_properties
        )
