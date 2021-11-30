"""Test the client class of AEH."""
from azure.eventhub.aio import EventHubProducerClient
import pytest

from homeassistant.components.azure_event_hub.client import (
    AzureEventHubClient,
    AzureEventHubClientConnectionString,
    AzureEventHubClientSAS,
    ClientCreationError,
)
from homeassistant.components.azure_event_hub.const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_NAMESPACE,
)

from .const import CS_CONFIG_FULL, SAS_CONFIG_FULL


@pytest.mark.parametrize(
    "config, subclass, policy_use, conn_str_use",
    [
        (SAS_CONFIG_FULL, AzureEventHubClientSAS, 1, 0),
        (CS_CONFIG_FULL, AzureEventHubClientConnectionString, 0, 1),
    ],
)
def test_create(
    config, subclass, policy_use, conn_str_use, mock_policy, mock_from_connection_string
):
    """Test the creation of the hubs for sas policy and key."""
    client = AzureEventHubClient.from_input(**config)
    assert isinstance(client, subclass)
    eh_client = client.client
    assert isinstance(eh_client, EventHubProducerClient)
    assert mock_policy.call_count == policy_use
    assert mock_from_connection_string.call_count == conn_str_use


async def test_test_connection(mock_get_eventhub_properties):
    """Test the test connection function."""
    client = AzureEventHubClient.from_input(**SAS_CONFIG_FULL)
    await client.test_connection()
    mock_get_eventhub_properties.assert_called_once()


@pytest.mark.parametrize(
    "config",
    [
        {},
        {CONF_EVENT_HUB_CON_STRING: "test"},
        {CONF_EVENT_HUB_NAMESPACE: "test"},
    ],
)
def test_create_error(config):
    """Test the creation errors."""
    try:
        AzureEventHubClient.from_input(**config)
    except Exception as err:  # pylint: disable=broad-except
        assert isinstance(err, ClientCreationError)
