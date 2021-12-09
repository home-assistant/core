"""Test fixtures for AEH."""
from dataclasses import dataclass
import logging
from unittest.mock import MagicMock, patch

from azure.eventhub.aio import EventHubProducerClient
import pytest

from homeassistant.components.azure_event_hub.const import DATA_FILTER, DATA_HUB, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

from .const import AZURE_EVENT_HUB_PATH, BASIC_OPTIONS, PRODUCER_PATH, SAS_CONFIG_FULL

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


# fixtures for both init and config flow tests
@pytest.fixture(autouse=True, name="mock_get_eventhub_properties")
def mock_get_eventhub_properties_fixture():
    """Mock azure event hub properties, used to test the connection."""
    with patch(f"{PRODUCER_PATH}.get_eventhub_properties") as get_eventhub_properties:
        yield get_eventhub_properties


@pytest.fixture(name="filter_schema")
def mock_filter_schema():
    """Return an empty filter."""
    yield {}


@pytest.fixture(name="entry")
async def mock_entry_fixture(hass, filter_schema, mock_create_batch):
    """Create the setup in HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    hass.data[DOMAIN] = {DATA_FILTER: FILTER_SCHEMA(filter_schema)}
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED

    # Clear the component_loaded event from the queue.
    await hass.data[DOMAIN][DATA_HUB].queue.get()
    hass.data[DOMAIN][DATA_HUB].queue.task_done()

    yield entry


# fixtures for init tests
@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    entity_id: str
    should_pass: bool


@pytest.fixture(name="mock_send_batch", scope="module")
def mock_send_batch_fixture():
    """Mock send_batch."""
    with patch(f"{PRODUCER_PATH}.send_batch") as mock_send_batch:
        yield mock_send_batch


@pytest.fixture(autouse=True, name="mock_client", scope="module")
def mock_client_fixture(mock_send_batch):
    """Mock the azure event hub producer client."""
    with patch(f"{PRODUCER_PATH}.close") as mock_close, patch(
        f"{PRODUCER_PATH}.__init__", return_value=None
    ) as mock_init:
        yield (
            mock_init,
            mock_send_batch,
            mock_close,
        )


@pytest.fixture(name="mock_create_batch")
def mock_create_batch_fixture():
    """Mock batch creator and return mocked batch object."""
    mock_batch = MagicMock()
    with patch(f"{PRODUCER_PATH}.create_batch", return_value=mock_batch):
        yield mock_batch


@pytest.fixture(name="hub")
async def mock_hub(hass, entry):
    """Use the entry and add a single test event to the queue."""
    assert entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][DATA_HUB].queue.qsize() == 0

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()

    assert hass.data[DOMAIN][DATA_HUB].queue.qsize() == 1
    yield hass.data[DOMAIN][DATA_HUB]


# fixtures for config flow tests
@pytest.fixture(name="mock_from_connection_string")
def mock_from_connection_string_fixture():
    """Mock AEH from connection string creation."""
    mock_aeh = MagicMock(spec=EventHubProducerClient)
    mock_aeh.__aenter__.return_value = mock_aeh
    with patch(
        f"{PRODUCER_PATH}.from_connection_string",
        return_value=mock_aeh,
    ) as from_conn_string:
        yield from_conn_string


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry():
    """Mock the setup entry call, used for config flow tests."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
