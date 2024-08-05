"""Setting up the Azure Data Explorer ingest client."""

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
    CONF_USE_QUEUED_CLIENT,
)

_LOGGER = logging.getLogger(__name__)


class AzureDataExplorerClient:
    """Class for Azure Data Explorer Client."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        """Create the right class."""

        self._database = data[CONF_ADX_DATABASE_NAME]
        self._table = data[CONF_ADX_TABLE_NAME]
        self._ingestion_properties = IngestionProperties(
            database=self._database,
            table=self._table,
            data_format=DataFormat.MULTIJSON,
            ingestion_mapping_reference="ha_json_mapping",
        )

        # Create client for ingesting data
        kcsb_ingest = (
            KustoConnectionStringBuilder.with_aad_application_key_authentication(
                data[CONF_ADX_CLUSTER_INGEST_URI],
                data[CONF_APP_REG_ID],
                data[CONF_APP_REG_SECRET],
                data[CONF_AUTHORITY_ID],
            )
        )

        # Create client for querying data
        kcsb_query = (
            KustoConnectionStringBuilder.with_aad_application_key_authentication(
                data[CONF_ADX_CLUSTER_INGEST_URI].replace("ingest-", ""),
                data[CONF_APP_REG_ID],
                data[CONF_APP_REG_SECRET],
                data[CONF_AUTHORITY_ID],
            )
        )

        if data[CONF_USE_QUEUED_CLIENT] is True:
            # Queued is the only option supported on free tier of ADX
            self.write_client = QueuedIngestClient(kcsb_ingest)
        else:
            self.write_client = ManagedStreamingIngestClient(kcsb_ingest)

        self.query_client = KustoClient(kcsb_query)

        # Reduce the HTTP logging, the default INFO logging is too verbose.
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
            logging.WARNING
        )

    def test_connection(self) -> None:
        """Test connection, will throw Exception if it cannot connect."""

        query = f"{self._table} | take 1"

        self.query_client.execute_query(self._database, query)

    def ingest_data(self, adx_events: str) -> None:
        """Send data to Azure Data Explorer."""

        bytes_stream = io.StringIO(adx_events)
        stream_descriptor = StreamDescriptor(bytes_stream)

        self.write_client.ingest_from_stream(
            stream_descriptor, ingestion_properties=self._ingestion_properties
        )
