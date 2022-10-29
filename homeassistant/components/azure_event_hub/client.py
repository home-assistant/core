"""File for Azure Event Hub models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

from azure.eventhub.aio import EventHubProducerClient, EventHubSharedKeyCredential

from .const import ADDITIONAL_ARGS, CONF_EVENT_HUB_CON_STRING

_LOGGER = logging.getLogger(__name__)


@dataclass
class AzureEventHubClient(ABC):
    """Class for the Azure Event Hub client. Use from_input to initialize."""

    event_hub_instance_name: str

    @property
    @abstractmethod
    def client(self) -> EventHubProducerClient:
        """Return the client."""

    async def test_connection(self) -> None:
        """Test connection, will throw EventHubError when it cannot connect."""
        async with self.client as client:
            await client.get_eventhub_properties()

    @classmethod
    def from_input(cls, **kwargs) -> AzureEventHubClient:
        """Create the right class."""
        if CONF_EVENT_HUB_CON_STRING in kwargs:
            return AzureEventHubClientConnectionString(**kwargs)
        return AzureEventHubClientSAS(**kwargs)


@dataclass
class AzureEventHubClientConnectionString(AzureEventHubClient):
    """Class for Connection String based Azure Event Hub Client."""

    event_hub_connection_string: str

    @property
    def client(self) -> EventHubProducerClient:
        """Return the client."""
        return EventHubProducerClient.from_connection_string(
            conn_str=self.event_hub_connection_string,
            eventhub_name=self.event_hub_instance_name,
            **ADDITIONAL_ARGS,
        )


@dataclass
class AzureEventHubClientSAS(AzureEventHubClient):
    """Class for SAS based Azure Event Hub Client."""

    event_hub_namespace: str
    event_hub_sas_policy: str
    event_hub_sas_key: str

    @property
    def client(self) -> EventHubProducerClient:
        """Get a Event Producer Client."""
        return EventHubProducerClient(
            fully_qualified_namespace=f"{self.event_hub_namespace}.servicebus.windows.net",
            eventhub_name=self.event_hub_instance_name,
            credential=EventHubSharedKeyCredential(  # type: ignore[arg-type]
                policy=self.event_hub_sas_policy, key=self.event_hub_sas_key
            ),
            **ADDITIONAL_ARGS,
        )
