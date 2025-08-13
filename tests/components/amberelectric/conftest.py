"""Provide common Amber fixtures."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

from amberelectric.models.interval import Interval
import pytest

from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN

from .helpers import (
    CONTROLLED_LOAD_CHANNEL,
    FEED_IN_CHANNEL,
    FORECASTS,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_CHANNEL,
    GENERAL_CHANNEL_WITH_RANGE,
    GENERAL_FORECASTS,
    GENERAL_ONLY_SITE_ID,
)

from tests.common import MockConfigEntry

MOCK_API_TOKEN = "psk_0000000000000000"


def create_amber_config_entry(
    site_id: str, entry_id: str, name: str
) -> MockConfigEntry:
    """Create an Amber config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_NAME: name,
            CONF_SITE_ID: site_id,
        },
        entry_id=entry_id,
    )


@pytest.fixture
def mock_amber_client() -> Generator[AsyncMock]:
    """Mock the Amber API client."""
    with patch(
        "homeassistant.components.amberelectric.amberelectric.AmberApi",
        autospec=True,
    ) as mock_client:
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amberelectric.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def general_channel_config_entry():
    """Generate the default Amber config entry."""
    return create_amber_config_entry(GENERAL_ONLY_SITE_ID, GENERAL_ONLY_SITE_ID, "home")


@pytest.fixture
async def general_channel_and_controlled_load_config_entry():
    """Generate the default Amber config entry for site with controlled load."""
    return create_amber_config_entry(
        GENERAL_AND_CONTROLLED_SITE_ID, GENERAL_AND_CONTROLLED_SITE_ID, "home"
    )


@pytest.fixture
async def general_channel_and_feed_in_config_entry():
    """Generate the default Amber config entry for site with feed in."""
    return create_amber_config_entry(
        GENERAL_AND_FEED_IN_SITE_ID, GENERAL_AND_FEED_IN_SITE_ID, "home"
    )


@pytest.fixture
def general_channel_prices() -> list[Interval]:
    """List containing general channel prices."""
    return GENERAL_CHANNEL


@pytest.fixture
def general_channel_prices_with_range() -> list[Interval]:
    """List containing general channel prices."""
    return GENERAL_CHANNEL_WITH_RANGE


@pytest.fixture
def controlled_load_channel_prices() -> list[Interval]:
    """List containing controlled load channel prices."""
    return CONTROLLED_LOAD_CHANNEL


@pytest.fixture
def feed_in_channel_prices() -> list[Interval]:
    """List containing feed in channel prices."""
    return FEED_IN_CHANNEL


@pytest.fixture
def forecast_prices() -> list[Interval]:
    """List containing forecasts with advanced prices."""
    return FORECASTS


@pytest.fixture
def general_forecast_prices() -> list[Interval]:
    """List containing forecasts with advanced prices."""
    return GENERAL_FORECASTS


@pytest.fixture
def mock_amber_client_general_channel(
    mock_amber_client: AsyncMock, general_channel_prices: list[Interval]
) -> Generator[AsyncMock]:
    """Fake general channel prices."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = general_channel_prices
    return mock_amber_client


@pytest.fixture
def mock_amber_client_general_channel_with_range(
    mock_amber_client: AsyncMock, general_channel_prices_with_range: list[Interval]
) -> Generator[AsyncMock]:
    """Fake general channel prices with a range."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = general_channel_prices_with_range
    return mock_amber_client


@pytest.fixture
def mock_amber_client_general_and_controlled_load(
    mock_amber_client: AsyncMock,
    general_channel_prices: list[Interval],
    controlled_load_channel_prices: list[Interval],
) -> Generator[AsyncMock]:
    """Fake general channel and controlled load channel prices."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = (
        general_channel_prices + controlled_load_channel_prices
    )
    return mock_amber_client


@pytest.fixture
async def mock_amber_client_general_and_feed_in(
    mock_amber_client: AsyncMock,
    general_channel_prices: list[Interval],
    feed_in_channel_prices: list[Interval],
) -> AsyncGenerator[Mock]:
    """Set up general channel and feed in channel."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = (
        general_channel_prices + feed_in_channel_prices
    )
    return mock_amber_client


@pytest.fixture
async def mock_amber_client_forecasts(
    mock_amber_client: AsyncMock, forecast_prices: list[Interval]
) -> AsyncGenerator[Mock]:
    """Set up general channel, controlled load and feed in channel."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = forecast_prices
    return mock_amber_client


@pytest.fixture
async def mock_amber_client_general_forecasts(
    mock_amber_client: AsyncMock, general_forecast_prices: list[Interval]
) -> AsyncGenerator[Mock]:
    """Set up general channel only."""
    client = mock_amber_client.return_value
    client.get_current_prices.return_value = general_forecast_prices
    return mock_amber_client
