"""Tests for the Amber Electric Data Coordinator."""
from __future__ import annotations

from collections.abc import Generator
from datetime import date
from unittest.mock import Mock, patch

from amberelectric import ApiException
from amberelectric.model.channel import Channel, ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.interval import Descriptor, SpikeStatus
from amberelectric.model.site import Site, SiteStatus
from dateutil import parser
import pytest

from homeassistant.components.amberelectric.coordinator import (
    AmberUpdateCoordinator,
    normalize_descriptor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .helpers import (
    CONTROLLED_LOAD_CHANNEL,
    FEED_IN_CHANNEL,
    GENERAL_AND_CONTROLLED_SITE_ID,
    GENERAL_AND_FEED_IN_SITE_ID,
    GENERAL_CHANNEL,
    GENERAL_ONLY_SITE_ID,
    generate_current_interval,
)


@pytest.fixture(name="current_price_api")
def mock_api_current_price() -> Generator:
    """Return an authentication error."""
    instance = Mock()

    general_site = Site(
        GENERAL_ONLY_SITE_ID,
        "11111111111",
        [Channel(identifier="E1", type=ChannelType.GENERAL, tariff="A100")],
        "Jemena",
        SiteStatus.ACTIVE,
        date(2021, 1, 1),
        None,
    )
    general_and_controlled_load = Site(
        GENERAL_AND_CONTROLLED_SITE_ID,
        "11111111112",
        [
            Channel(identifier="E1", type=ChannelType.GENERAL, tariff="A100"),
            Channel(identifier="E2", type=ChannelType.CONTROLLED_LOAD, tariff="A180"),
        ],
        "Jemena",
        SiteStatus.ACTIVE,
        date(2021, 1, 1),
        None,
    )
    general_and_feed_in = Site(
        GENERAL_AND_FEED_IN_SITE_ID,
        "11111111113",
        [
            Channel(identifier="E1", type=ChannelType.GENERAL, tariff="A100"),
            Channel(identifier="E2", type=ChannelType.FEED_IN, tariff="A100"),
        ],
        "Jemena",
        SiteStatus.ACTIVE,
        date(2021, 1, 1),
        None,
    )
    instance.get_sites.return_value = [
        general_site,
        general_and_controlled_load,
        general_and_feed_in,
    ]

    with patch("amberelectric.api.AmberApi.create", return_value=instance):
        yield instance


def test_normalize_descriptor() -> None:
    """Test normalizing descriptors works correctly."""
    assert normalize_descriptor(None) is None
    assert normalize_descriptor(Descriptor.NEGATIVE) == "negative"
    assert normalize_descriptor(Descriptor.EXTREMELY_LOW) == "extremely_low"
    assert normalize_descriptor(Descriptor.VERY_LOW) == "very_low"
    assert normalize_descriptor(Descriptor.LOW) == "low"
    assert normalize_descriptor(Descriptor.NEUTRAL) == "neutral"
    assert normalize_descriptor(Descriptor.HIGH) == "high"
    assert normalize_descriptor(Descriptor.SPIKE) == "spike"


async def test_fetch_general_site(hass: HomeAssistant, current_price_api: Mock) -> None:
    """Test fetching a site with only a general channel."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    data_service = AmberUpdateCoordinator(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    result = await data_service._async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_ONLY_SITE_ID, next=48
    )

    assert result["current"].get("general") == GENERAL_CHANNEL[0]
    assert result["forecasts"].get("general") == [
        GENERAL_CHANNEL[1],
        GENERAL_CHANNEL[2],
        GENERAL_CHANNEL[3],
    ]
    assert result["current"].get("controlled_load") is None
    assert result["forecasts"].get("controlled_load") is None
    assert result["current"].get("feed_in") is None
    assert result["forecasts"].get("feed_in") is None
    assert result["grid"]["renewables"] == round(GENERAL_CHANNEL[0].renewables)
    assert result["grid"]["price_spike"] == "none"


async def test_fetch_no_general_site(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with no general channel."""

    current_price_api.get_current_price.return_value = CONTROLLED_LOAD_CHANNEL
    data_service = AmberUpdateCoordinator(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    with pytest.raises(UpdateFailed):
        await data_service._async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_ONLY_SITE_ID, next=48
    )


async def test_fetch_api_error(hass: HomeAssistant, current_price_api: Mock) -> None:
    """Test that the old values are maintained if a second call fails."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL
    data_service = AmberUpdateCoordinator(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    result = await data_service._async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_ONLY_SITE_ID, next=48
    )

    assert result["current"].get("general") == GENERAL_CHANNEL[0]
    assert result["forecasts"].get("general") == [
        GENERAL_CHANNEL[1],
        GENERAL_CHANNEL[2],
        GENERAL_CHANNEL[3],
    ]
    assert result["current"].get("controlled_load") is None
    assert result["forecasts"].get("controlled_load") is None
    assert result["current"].get("feed_in") is None
    assert result["forecasts"].get("feed_in") is None
    assert result["grid"]["renewables"] == round(GENERAL_CHANNEL[0].renewables)

    current_price_api.get_current_price.side_effect = ApiException(status=403)
    with pytest.raises(UpdateFailed):
        await data_service._async_update_data()

    assert result["current"].get("general") == GENERAL_CHANNEL[0]
    assert result["forecasts"].get("general") == [
        GENERAL_CHANNEL[1],
        GENERAL_CHANNEL[2],
        GENERAL_CHANNEL[3],
    ]
    assert result["current"].get("controlled_load") is None
    assert result["forecasts"].get("controlled_load") is None
    assert result["current"].get("feed_in") is None
    assert result["forecasts"].get("feed_in") is None
    assert result["grid"]["renewables"] == round(GENERAL_CHANNEL[0].renewables)
    assert result["grid"]["price_spike"] == "none"


async def test_fetch_general_and_controlled_load_site(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with a general and controlled load channel."""

    current_price_api.get_current_price.return_value = (
        GENERAL_CHANNEL + CONTROLLED_LOAD_CHANNEL
    )
    data_service = AmberUpdateCoordinator(
        hass, current_price_api, GENERAL_AND_CONTROLLED_SITE_ID
    )
    result = await data_service._async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_AND_CONTROLLED_SITE_ID, next=48
    )

    assert result["current"].get("general") == GENERAL_CHANNEL[0]
    assert result["forecasts"].get("general") == [
        GENERAL_CHANNEL[1],
        GENERAL_CHANNEL[2],
        GENERAL_CHANNEL[3],
    ]
    assert result["current"].get("controlled_load") is CONTROLLED_LOAD_CHANNEL[0]
    assert result["forecasts"].get("controlled_load") == [
        CONTROLLED_LOAD_CHANNEL[1],
        CONTROLLED_LOAD_CHANNEL[2],
        CONTROLLED_LOAD_CHANNEL[3],
    ]
    assert result["current"].get("feed_in") is None
    assert result["forecasts"].get("feed_in") is None
    assert result["grid"]["renewables"] == round(GENERAL_CHANNEL[0].renewables)
    assert result["grid"]["price_spike"] == "none"


async def test_fetch_general_and_feed_in_site(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with a general and feed_in channel."""

    current_price_api.get_current_price.return_value = GENERAL_CHANNEL + FEED_IN_CHANNEL
    data_service = AmberUpdateCoordinator(
        hass, current_price_api, GENERAL_AND_FEED_IN_SITE_ID
    )
    result = await data_service._async_update_data()

    current_price_api.get_current_price.assert_called_with(
        GENERAL_AND_FEED_IN_SITE_ID, next=48
    )

    assert result["current"].get("general") == GENERAL_CHANNEL[0]
    assert result["forecasts"].get("general") == [
        GENERAL_CHANNEL[1],
        GENERAL_CHANNEL[2],
        GENERAL_CHANNEL[3],
    ]
    assert result["current"].get("controlled_load") is None
    assert result["forecasts"].get("controlled_load") is None
    assert result["current"].get("feed_in") is FEED_IN_CHANNEL[0]
    assert result["forecasts"].get("feed_in") == [
        FEED_IN_CHANNEL[1],
        FEED_IN_CHANNEL[2],
        FEED_IN_CHANNEL[3],
    ]
    assert result["grid"]["renewables"] == round(GENERAL_CHANNEL[0].renewables)
    assert result["grid"]["price_spike"] == "none"


async def test_fetch_potential_spike(
    hass: HomeAssistant, current_price_api: Mock
) -> None:
    """Test fetching a site with only a general channel."""

    general_channel: list[CurrentInterval] = [
        generate_current_interval(
            ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
        ),
    ]
    general_channel[0].spike_status = SpikeStatus.POTENTIAL
    current_price_api.get_current_price.return_value = general_channel
    data_service = AmberUpdateCoordinator(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    result = await data_service._async_update_data()
    assert result["grid"]["price_spike"] == "potential"


async def test_fetch_spike(hass: HomeAssistant, current_price_api: Mock) -> None:
    """Test fetching a site with only a general channel."""

    general_channel: list[CurrentInterval] = [
        generate_current_interval(
            ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
        ),
    ]
    general_channel[0].spike_status = SpikeStatus.SPIKE
    current_price_api.get_current_price.return_value = general_channel
    data_service = AmberUpdateCoordinator(hass, current_price_api, GENERAL_ONLY_SITE_ID)
    result = await data_service._async_update_data()
    assert result["grid"]["price_spike"] == "spike"
