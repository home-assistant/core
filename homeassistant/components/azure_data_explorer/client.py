"""Setting up the ingest client."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class AzureDataExplorerClient:
    """Class for Azure Data Explorer Client."""

    def __init__(self, **kwargs) -> None:
        """Create the right class."""

        cluster_ingest_uri = kwargs.get("clusteringesturi")
        cluster_query_uri = str(cluster_ingest_uri).replace("ingest-", "")
        self.database = kwargs.get("database")
        self.table = kwargs.get("table")
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")
        authority_id = kwargs.get("authority_id")
        use_queued_ingestion = kwargs.get("use_free_cluster")

        # Create cLient for ingesting data
        kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(
            cluster_ingest_uri, client_id, client_secret, authority_id
        )

        if (
            use_queued_ingestion is True
        ):  # Queded is the only option supported on free tear of ADX
            self.client = QueuedIngestClient(kcsb)
        else:
            self.client = ManagedStreamingIngestClient.from_dm_kcsb(kcsb)

        # Create cLient for quereing data
        kcsbq = KustoConnectionStringBuilder.with_aad_application_key_authentication(
            cluster_query_uri, client_id, client_secret, authority_id
        )

        self.query_client = KustoClient(kcsbq)

        # Suppress very verbose logging from client
        logger = logging.getLogger("azure")
        logger.setLevel(logging.WARNING)

    # async def test_connection_async(self) -> True:
    #   """Async Test connection, will throw Exception when it cannot connect."""
    #   # kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(cluster, client_id, client_secret, authority_id)
    #   async with self.query_client as client:
    #       query = query = self.table + " | take 1"

    #       try:
    #           response = await client.execute(self.database, query)
    #       except Exception as exp:
    #           _LOGGER.error(
    #               "************* Error connection to ADX ******************"
    #           )
    #           _LOGGER.error(exp)
    #           return Exception
    #       return True

    def test_connection(self) -> None:
        """Test connection, will throw Exception when it cannot connect."""

        query = "%s | take 1" % self.table

        self.query_client.execute(self.database, query)

        return None

    def ingest_data(self, adx_events) -> Exception | None:
        """Send data to Axure Data Explorer."""

        ingestion_properties = IngestionProperties(
            database=self.database,
            table=self.table,
            data_format=DataFormat.MULTIJSON,
            ingestion_mapping_reference="ha_json_mapping",
        )

        json_str = adx_events

        try:
            bytes_stream = io.StringIO(json_str)
            stream_descriptor = StreamDescriptor(bytes_stream)

            self.client.ingest_from_stream(
                stream_descriptor, ingestion_properties=ingestion_properties
            )

        except Exception as exp:  # pylint: disable=broad-except
            _LOGGER.error(exp)
            return exp
        return None
