"""Test fixtures for AEH."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.azure_event_hub.client import (
    AzureEventHubClient,
    EventHubProducerClient,
)
from homeassistant.components.azure_event_hub.hub import AzureEventHub

from .const import AZURE_EVENT_HUB_PATH, CONFIG_FLOW_PATH, PRODUCER_PATH


@pytest.fixture(autouse=False, name="mock_aeh")
def mock_aeh_client_fixture():
    """Mock the azure event hub client."""
    with patch(
        f"{CONFIG_FLOW_PATH}.AzureEventHubClient.from_input",
        return_value=Mock(spec=AzureEventHubClient),
    ) as mock_aeh_client:
        yield mock_aeh_client


@pytest.fixture(autouse=True, name="mock_client", scope="module")
def mock_client_fixture():
    """Mock the azure event hub producer client."""
    with patch(f"{PRODUCER_PATH}.send_batch") as mock_send_batch, patch(
        f"{PRODUCER_PATH}.close"
    ) as mock_close, patch(f"{PRODUCER_PATH}.__init__", return_value=None) as mock_init:
        yield (
            mock_init,
            mock_send_batch,
            mock_close,
        )


@pytest.fixture(autouse=True, name="mock_batch")
def mock_batch_fixture():
    """Mock batch creator and return mocked batch object."""
    mock_batch = MagicMock()
    with patch(f"{PRODUCER_PATH}.create_batch", return_value=mock_batch):
        yield mock_batch


@pytest.fixture(autouse=True, name="mock_policy")
def mock_policy_fixture():
    """Mock azure shared key credential."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.client.EventHubSharedKeyCredential") as policy:
        yield policy


@pytest.fixture(autouse=True, name="mock_from_connection_string")
def mock_from_connection_string_fixture():
    """Mock azure shared key credential."""
    with patch(
        f"{PRODUCER_PATH}.from_connection_string",
        return_value=Mock(spec=EventHubProducerClient),
    ) as from_conn_string:
        yield from_conn_string


@pytest.fixture(autouse=True, name="mock_get_eventhub_properties")
def mock_get_eventhub_properties_fixture():
    """Mock azure event hub properties, used to test the connection."""
    with patch(f"{PRODUCER_PATH}.get_eventhub_properties") as get_eventhub_properties:
        yield get_eventhub_properties


@pytest.fixture(autouse=True, name="mock_event_data")
def mock_event_data_fixture():
    """Mock the azure event data component."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.hub.EventData") as event_data:
        yield event_data


@pytest.fixture(autouse=True, name="mock_call_later")
def mock_call_later_fixture():
    """Mock async_call_later to allow queue processing on demand."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.hub.async_call_later") as mock_call_later:
        yield mock_call_later


@pytest.fixture
def mock_setup_entry():
    """Mock the azure event data component."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_hub():
    """Mock the Hub."""
    hub = Mock(spec=AzureEventHub)
    with patch(f"{AZURE_EVENT_HUB_PATH}.AzureEventHub", return_value=hub) as mocked_hub:
        yield mocked_hub
