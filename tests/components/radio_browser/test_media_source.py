"""Tests for radio_browser media_source."""

from unittest.mock import AsyncMock

import pytest
from radios import FilterBy, Order

from homeassistant.components import media_source
from homeassistant.components.radio_browser.media_source import async_get_media_source
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "radio_browser"


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def test_browsing_local(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test browsing local stations."""

    hass.config.latitude = 45.58539
    hass.config.longitude = -122.40320
    hass.config.country = "US"

    source = await async_get_media_source(hass)
    patch_radios(source)

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}"
    )

    assert item is not None
    assert item.title == "My Radios"
    assert item.children is not None
    assert len(item.children) == 5
    assert item.can_play is False
    assert item.can_expand is True

    assert item.children[3].title == "Local stations"

    item_child = await media_source.async_browse_media(
        hass, item.children[3].media_content_id
    )

    source.radios.stations.assert_awaited_with(
        filter_by=FilterBy.COUNTRY_CODE_EXACT,
        filter_term=hass.config.country,
        hide_broken=True,
        order=Order.NAME,
        reverse=False,
    )

    assert item_child is not None
    assert item_child.title == "My Radios"
    assert len(item_child.children) == 2
    assert item_child.children[0].title == "Near Station 1"
    assert item_child.children[1].title == "Near Station 2"

    # Test browsing a different category to hit the path where async_build_local
    # returns []
    other_browse = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/nonexistent"
    )

    assert other_browse is not None
    assert other_browse.title == "My Radios"
    assert len(other_browse.children) == 0


async def test_search_stations(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test server-side search for radio stations by name."""
    source = await async_get_media_source(hass)
    patch_radios(source)

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/search/rock"
    )

    source.radios.stations.assert_awaited_with(
        filter_by=FilterBy.NAME,
        filter_term="rock",
        hide_broken=True,
        limit=100,
        order=Order.CLICK_COUNT,
        reverse=True,
    )

    assert item is not None
    assert item.children is not None
    assert len(item.children) > 0


async def test_search_stations_with_codec_filter(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test server-side search filtered by codec (e.g. AAC for Apple TV)."""
    source = await async_get_media_source(hass)
    patch_radios(source)

    # The mock stations all have codec "MP3", so filtering for AAC returns nothing
    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/search/rock/AAC"
    )

    source.radios.stations.assert_awaited_with(
        filter_by=FilterBy.NAME,
        filter_term="rock",
        hide_broken=True,
        limit=100,
        order=Order.CLICK_COUNT,
        reverse=True,
    )

    # Mock stations are all MP3, so AAC filter yields empty result
    assert item is not None
    assert item.children == []


async def test_search_stations_with_codec_filter_case_insensitive(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test that codec filter is case-insensitive."""
    source = await async_get_media_source(hass)
    patch_radios(source)

    # Mock stations are all MP3 — search with lowercase "mp3" should still match
    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/search/rock/mp3"
    )

    assert item is not None
    assert item.children is not None
    assert len(item.children) > 0


async def test_search_stations_empty_query(
    hass: HomeAssistant, init_integration: AsyncMock, patch_radios
) -> None:
    """Test that an empty search query returns no results without calling the API."""
    source = await async_get_media_source(hass)
    patch_radios(source)

    item = await media_source.async_browse_media(
        hass, f"{media_source.URI_SCHEME}{DOMAIN}/search/"
    )

    source.radios.stations.assert_not_awaited()

    assert item is not None
    assert item.children == []
