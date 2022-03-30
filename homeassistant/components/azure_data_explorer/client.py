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


class AzureDataExplorerClient:
    """Class for Azure Data Explorer Client."""

    def __init__(
        self,
        clusteringesturi: str,
        database: str,
        table: str,
        client_id: str,
        client_secret: str,
        authority_id: str,
        use_free_cluster: bool,
    ) -> None:
        """Create the right class."""

        self.cluster_ingest_uri = clusteringesturi
        self.database = database
        self.table = table
        self.client_id = client_id
        self.client_secret = client_secret
        self.authority_id = authority_id
        self.use_queued_ingestion = use_free_cluster

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
            self.cluster_ingest_uri, client_id, client_secret, authority_id
        )

        if (
            self.use_queued_ingestion is True
        ):  # Queded is the only option supported on free tear of ADX
            self.client = QueuedIngestClient(kcsb)
        else:
            self.client = ManagedStreamingIngestClient.from_dm_kcsb(kcsb)

        kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(
            self.cluster_query_uri, client_id, client_secret, authority_id
        )

        self.query_client = KustoClient(kcsb)

        # Suppress very verbose logging from client
        logger = logging.getLogger("azure")
        logger.setLevel(logging.WARNING)

    def test_connection(self) -> None:
        """Test connection, will throw Exception when it cannot connect."""

        query = "%s | take 1" % self.table

        self.query_client.execute_query(self.database, query)

    def ingest_data(self, adx_events: str) -> None:
        """Send data to Axure Data Explorer."""

        bytes_stream = io.StringIO(adx_events)
        stream_descriptor = StreamDescriptor(bytes_stream)

        self.client.ingest_from_stream(
            stream_descriptor, ingestion_properties=self.ingestion_properties
        )
