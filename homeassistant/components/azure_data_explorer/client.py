"""Setting up the ingest client."""
from __future__ import annotations

from collections.abc import Mapping
import io
import logging
from typing import Any

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import (
    IngestionProperties,
    ManagedStreamingIngestClient,
    QueuedIngestClient,
    StreamDescriptor,
)

from .const import (
    CONF_ADX_CLUSTER_INGEST_URI,
    CONF_ADX_DATABASE_NAME,
    CONF_ADX_TABLE_NAME,
    CONF_APP_REG_ID,
    CONF_APP_REG_SECRET,
    CONF_AUTHORITY_ID,
    CONF_USE_FREE,
)

_LOGGER = logging.getLogger(__name__)

# Suppress very verbose logging from client
logger = logging.getLogger("azure")
logger.setLevel(logging.WARNING)


class AzureDataExplorerClient:
    """Class for Azure Data Explorer Client."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        """Create the right class."""

        self.cluster_ingest_uri = data[CONF_ADX_CLUSTER_INGEST_URI]
        self.database = data[CONF_ADX_DATABASE_NAME]
        self.table = data[CONF_ADX_TABLE_NAME]
        self.client_id = data[CONF_APP_REG_ID]
        self.client_secret = data[CONF_APP_REG_SECRET]
        self.authority_id = data[CONF_AUTHORITY_ID]
        self.use_queued_ingestion = data[CONF_USE_FREE]

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
