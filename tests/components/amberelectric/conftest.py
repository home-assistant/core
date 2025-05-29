"""Provide common Amber fixtures."""

from collections.abc import AsyncGenerator, Generator
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

from amberelectric.models.channel import Channel, ChannelType
from amberelectric.models.interval import Interval
from amberelectric.models.range import Range
from amberelectric.models.site import Site
from amberelectric.models.site_status import SiteStatus
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
    GENERAL_ONLY_SITE_ID,
)

from tests.common import MockConfigEntry

MOCK_API_TOKEN = "psk_0000000000000000"


def create_amber_config_entry(site_id: str, name: str) -> MockConfigEntry:
    """Create an Amber config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_NAME: name,
            CONF_SITE_ID: site_id,
        },
        unique_id=site_id,
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
    return create_amber_config_entry(GENERAL_ONLY_SITE_ID, "home")


@pytest.fixture
async def general_channel_and_controlled_load_config_entry():
    """Generate the default Amber config entry for site with controlled load."""
    return create_amber_config_entry(GENERAL_AND_CONTROLLED_SITE_ID, "home")


@pytest.fixture
async def general_channel_and_feed_in_config_entry():
    """Generate the default Amber config entry for site with feed in."""
    return create_amber_config_entry(GENERAL_AND_FEED_IN_SITE_ID, "home")


@pytest.fixture
def general_channel_prices() -> list[Interval]:
    """List containing general channel prices."""
    return GENERAL_CHANNEL


@pytest.fixture
def controlled_load_channel_prices() -> list[Interval]:
    """List containing controlled load channel prices."""
    return CONTROLLED_LOAD_CHANNEL


@pytest.fixture
def feed_in_channel_prices() -> list[Interval]:
    """List containing feed in channel prices."""
    return FEED_IN_CHANNEL


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
    mock_amber_client: AsyncMock, general_channel_prices: list[Interval]
) -> Generator[AsyncMock]:
    """Fake general channel prices with a range."""
    for interval in general_channel_prices:
        interval.actual_instance.range = Range(min=7.8, max=12.4)

    client = mock_amber_client.return_value
    client.get_current_prices.return_value = general_channel_prices
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


@pytest.fixture(name="forecast_prices")
def mock_api_current_price() -> Generator:
    """Return an authentication error."""
    instance = Mock()

    site = Site(
        id=GENERAL_ONLY_SITE_ID,
        nmi="11111111111",
        channels=[
            Channel(identifier="E1", type=ChannelType.GENERAL, tariff="A100"),
            Channel(identifier="E2", type=ChannelType.CONTROLLEDLOAD, tariff="A180"),
            Channel(identifier="B1", type=ChannelType.FEEDIN, tariff="A100"),
        ],
        network="Jemena",
        status=SiteStatus("active"),
        activeFrom=date(2021, 1, 1),
        closedOn=None,
        interval_length=30,
    )

    instance.get_sites = Mock(return_value=[site])
    instance.get_current_prices = Mock(return_value=FORECASTS)

    with patch("amberelectric.AmberApi", return_value=instance):
        yield instance
