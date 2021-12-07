"""File for Azure Event Hub models."""
from __future__ import annotations

from dataclasses import dataclass

from azure.eventhub.aio import EventHubProducerClient, EventHubSharedKeyCredential

from homeassistant.exceptions import HomeAssistantError

from .const import ADDITIONAL_ARGS, CONF_EVENT_HUB_CON_STRING


@dataclass
class AzureEventHubClient:
    """Class for the Azure Event Hub client. Use from_input to initialize."""

    event_hub_instance_name: str

    @property
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
            try:
                return AzureEventHubClientConnectionString(**kwargs)
            except TypeError as exc:
                raise ClientCreationError(
                    "Could not create AEH client from connection string."
                ) from exc
        try:
            return AzureEventHubClientSAS(**kwargs)
        except TypeError as exc:
            raise ClientCreationError(
                "Could not create AEH client from SAS credentials"
            ) from exc


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
            credential=EventHubSharedKeyCredential(  # type: ignore
                policy=self.event_hub_sas_policy, key=self.event_hub_sas_key
            ),
            **ADDITIONAL_ARGS,
        )


class ClientCreationError(HomeAssistantError):
    """Error creating client."""
