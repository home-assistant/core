"""Test fixtures for AEH."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from azure.eventhub.aio import EventHubProducerClient
import pytest

from homeassistant.components.azure_event_hub.const import (
    CONF_FILTER,
    CONF_SEND_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import AZURE_EVENT_HUB_PATH, BASIC_OPTIONS, PRODUCER_PATH, SAS_CONFIG_FULL

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


# fixtures for both init and config flow tests
@pytest.fixture(autouse=True, name="mock_get_eventhub_properties")
def mock_get_eventhub_properties_fixture() -> Generator[AsyncMock]:
    """Mock azure event hub properties, used to test the connection."""
    with patch(f"{PRODUCER_PATH}.get_eventhub_properties") as get_eventhub_properties:
        yield get_eventhub_properties


@pytest.fixture(name="filter_schema")
def mock_filter_schema() -> dict[str, Any]:
    """Return an empty filter."""
    return {}


@pytest.fixture(name="entry")
async def mock_entry_fixture(
    hass: HomeAssistant,
    filter_schema: dict[str, Any],
    mock_create_batch: MagicMock,
    mock_send_batch: AsyncMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Create the setup in HA."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_FILTER: filter_schema}}
    )
    assert entry.state is ConfigEntryState.LOADED

    # Clear the component_loaded event from the queue.
    async_fire_time_changed(
        hass,
        utcnow() + timedelta(seconds=entry.options[CONF_SEND_INTERVAL]),
    )
    await hass.async_block_till_done()

    yield entry

    await hass.config_entries.async_unload(entry.entry_id)


# fixtures for init tests
@pytest.fixture(name="entry_with_one_event")
def mock_entry_with_one_event(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Use the entry and add a single test event to the queue."""
    assert entry.state is ConfigEntryState.LOADED
    hass.states.async_set("sensor.test", STATE_ON)
    return entry


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    entity_id: str
    expected_count: int


@pytest.fixture(name="mock_send_batch")
def mock_send_batch_fixture() -> Generator[AsyncMock]:
    """Mock send_batch."""
    with patch(f"{PRODUCER_PATH}.send_batch") as mock_send_batch:
        yield mock_send_batch


@pytest.fixture(autouse=True, name="mock_client")
def mock_client_fixture(
    mock_send_batch: AsyncMock,
) -> Generator[tuple[AsyncMock, AsyncMock]]:
    """Mock the azure event hub producer client."""
    with patch(f"{PRODUCER_PATH}.close") as mock_close:
        yield (
            mock_send_batch,
            mock_close,
        )


@pytest.fixture(name="mock_create_batch")
def mock_create_batch_fixture() -> Generator[MagicMock]:
    """Mock batch creator and return mocked batch object."""
    mock_batch = MagicMock()
    with patch(f"{PRODUCER_PATH}.create_batch", return_value=mock_batch):
        yield mock_batch


# fixtures for config flow tests
@pytest.fixture(name="mock_from_connection_string")
def mock_from_connection_string_fixture() -> Generator[MagicMock]:
    """Mock AEH from connection string creation."""
    mock_aeh = MagicMock(spec=EventHubProducerClient)
    mock_aeh.__aenter__.return_value = mock_aeh
    with patch(
        f"{PRODUCER_PATH}.from_connection_string",
        return_value=mock_aeh,
    ) as from_conn_string:
        yield from_conn_string


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry call, used for config flow tests."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
