"""Tests for the Amber Electric Data Coordinator."""
from typing import Generator
from unittest.mock import Mock, patch

from amberelectric import ApiException
from amberelectric.model.channel import Channel, ChannelType
from amberelectric.model.site import Site
import pytest

from homeassistant.components.amberelectric.coordinator import AmberDataService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.components.amberelectric.helpers import (
    CONTROLLED_LOAD_CHANNEL,
    FEED_IN_CHANNEL,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_CHANNEL,
    GENERAL_ONLY_SITE_ID,
)


@pytest.fixture(name="current_price_api")
def mock_api_current_price() -> Generator:
    """Return an authentication error."""
    instance = Mock()

    general_site = Site(
        GENERAL_ONLY_SITE_ID,
        "11111111111",
        [Channel(identifier="E1", type=ChannelType.GENERAL)],
    )
    general_and_controlled_load = Site(
        GENERAL_AND_CONTROLLED_SITE_ID,
        "11111111112",
        [
            Channel(identifier="E1", type=ChannelType.GENERAL),
            Channel(identifier="E2", type=ChannelType.CONTROLLED_LOAD),
        ],
    )
    general_and_feed_in = Site(
        GENERAL_AND_FEED_IN_SITE_ID,
        "11111111113",
        [
            Channel(identifier="E1", type=ChannelType.GENERAL),
            Channel(identifier="E2", type=ChannelType.FEED_IN),
        ],
    )
    instance.get_sites.return_value = [
        general_site,
        general_and_controlled_load,
        general_and_feed_in,
    ]

    with patch("amberelectric.api.AmberApi.create", return_value=instance):
        yield instance


async def test_fetch_general_site(hass: HomeAssistant, current_price_api: Mock) -> None:
    """Test fetching a site with only a general channel."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    data_service = AmberDataService(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    await data_service.async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_ONLY_SITE_ID, next=48
    )

    assert data_service.data == GENERAL_CHANNEL
    assert data_service.current_prices[ChannelType.GENERAL] == GENERAL_CHANNEL[1]
    assert data_service.forecasts[ChannelType.GENERAL] == [GENERAL_CHANNEL[2]]
    assert data_service.current_prices[ChannelType.CONTROLLED_LOAD] is None
    assert data_service.forecasts[ChannelType.CONTROLLED_LOAD] == []
    assert data_service.current_prices[ChannelType.FEED_IN] is None
    assert data_service.forecasts[ChannelType.FEED_IN] == []


async def test_fetch_api_error(hass: HomeAssistant, current_price_api: Mock) -> None:
    """Test that the old values are maintained if a second call fails."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    data_service = AmberDataService(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    await data_service.async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_ONLY_SITE_ID, next=48
    )

    assert data_service.data == GENERAL_CHANNEL
    assert data_service.current_prices[ChannelType.GENERAL] == GENERAL_CHANNEL[1]
    assert data_service.forecasts[ChannelType.GENERAL] == [GENERAL_CHANNEL[2]]
    assert data_service.current_prices[ChannelType.CONTROLLED_LOAD] is None
    assert data_service.forecasts[ChannelType.CONTROLLED_LOAD] == []
    assert data_service.current_prices[ChannelType.FEED_IN] is None
    assert data_service.forecasts[ChannelType.FEED_IN] == []

    current_price_api.get_current_price.side_effect = ApiException(status=403)
    with pytest.raises(UpdateFailed):
        await data_service.async_update_data()

    assert data_service.data == GENERAL_CHANNEL
    assert data_service.current_prices[ChannelType.GENERAL] == GENERAL_CHANNEL[1]
    assert data_service.forecasts[ChannelType.GENERAL] == [GENERAL_CHANNEL[2]]
    assert data_service.current_prices[ChannelType.CONTROLLED_LOAD] is None
    assert data_service.forecasts[ChannelType.CONTROLLED_LOAD] == []
    assert data_service.current_prices[ChannelType.FEED_IN] is None
    assert data_service.forecasts[ChannelType.FEED_IN] == []


async def test_fetch_general_and_controlled_load_site(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with a general and controlled load channel."""

    current_price_api.get_current_price.return_value = (
        GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
    )
    data_service = AmberDataService(
        hass, current_price_api, GENERAL_AND_CONTROLLED_SITE_ID
    )
    await data_service.async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_AND_CONTROLLED_SITE_ID, next=48
    )

    assert data_service.data == GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
    assert data_service.current_prices[ChannelType.GENERAL] == GENERAL_CHANNEL[1]
    assert data_service.forecasts[ChannelType.GENERAL] == [GENERAL_CHANNEL[2]]
    assert (
        data_service.current_prices[ChannelType.CONTROLLED_LOAD]
        == CONTROLLED_LOAD_CHANNEL[1]
    )
    assert data_service.forecasts[ChannelType.CONTROLLED_LOAD] == [
        CONTROLLED_LOAD_CHANNEL[2]
    ]
    assert data_service.current_prices[ChannelType.FEED_IN] is None
    assert data_service.forecasts[ChannelType.FEED_IN] == []


async def test_fetch_general_and_feed_in_site(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with a general and feed_in channel."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL + FEED_IN_CHANNEL
    data_service = AmberDataService(
        hass, current_price_api, GENERAL_AND_FEED_IN_SITE_ID
    )
    await data_service.async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_AND_FEED_IN_SITE_ID, next=48
    )

    assert data_service.data == GENERAL_CHANNEL + FEED_IN_CHANNEL
    assert data_service.current_prices[ChannelType.GENERAL] == GENERAL_CHANNEL[1]
    assert data_service.forecasts[ChannelType.GENERAL] == [GENERAL_CHANNEL[2]]
    assert data_service.current_prices[ChannelType.CONTROLLED_LOAD] is None
    assert data_service.forecasts[ChannelType.CONTROLLED_LOAD] == []
    assert data_service.current_prices[ChannelType.FEED_IN] == FEED_IN_CHANNEL[1]
    assert data_service.forecasts[ChannelType.FEED_IN] == [FEED_IN_CHANNEL[2]]
