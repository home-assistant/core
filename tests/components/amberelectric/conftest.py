"""Provide common Amber fixtures."""

from collections.abc import AsyncGenerator, Generator
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

from amberelectric.models.channel import Channel, ChannelType
from amberelectric.models.site import Site
from amberelectric.models.site_status import SiteStatus
import pytest

from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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


async def create_amber_config_entry(site_id: str) -> MockConfigEntry:
    """Create an Amber config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "TOKEN",
            CONF_SITE_NAME: "home",
            CONF_SITE_ID: site_id,
        },
        entry_id=site_id,
    )


@pytest.fixture
async def general_only_site_id_amber_config_entry():
    """Generate the default Amber config entry."""
    return await create_amber_config_entry(GENERAL_ONLY_SITE_ID)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amberelectric.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def setup_general(hass: HomeAssistant) -> AsyncGenerator[Mock]:
    """Set up general channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_SITE_NAME: "mock_title",
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_ONLY_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(return_value=GENERAL_CHANNEL)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_general_and_controlled_load(
    hass: HomeAssistant,
) -> AsyncGenerator[Mock]:
    """Set up general channel and controller load channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_AND_CONTROLLED_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(
            return_value=GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
        )
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_general_and_feed_in(hass: HomeAssistant) -> AsyncGenerator[Mock]:
    """Set up general channel and feed in channel."""
    MockConfigEntry(
        domain="amberelectric",
        data={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_SITE_ID: GENERAL_AND_FEED_IN_SITE_ID,
        },
    ).add_to_hass(hass)

    instance = Mock()
    with patch(
        "amberelectric.AmberApi",
        return_value=instance,
    ) as mock_update:
        instance.get_current_prices = Mock(
            return_value=GENERAL_CHANNEL + FEED_IN_CHANNEL
        )
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


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
