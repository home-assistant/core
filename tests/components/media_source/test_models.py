"""Test Media Source model methods."""

import pytest

from homeassistant.components.media_player import (
    MediaClass,
    MediaType,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import const, models
from homeassistant.components.media_source.const import MEDIA_SOURCE_DATA
from homeassistant.core import HomeAssistant


async def test_browse_media_as_dict() -> None:
    """Test BrowseMediaSource conversion to media player item dict."""
    base = models.BrowseMediaSource(
        domain=const.DOMAIN,
        identifier="media",
        media_class=MediaClass.DIRECTORY,
        media_content_type="folder",
        title="media/",
        can_play=False,
        can_expand=True,
        children_media_class=MediaClass.MUSIC,
    )
    base.children = [
        models.BrowseMediaSource(
            domain=const.DOMAIN,
            identifier="media/test.mp3",
            media_class=MediaClass.MUSIC,
            media_content_type=MediaType.MUSIC,
            title="test.mp3",
            can_play=True,
            can_expand=False,
        )
    ]

    item = base.as_dict()
    assert item["title"] == "media/"
    assert item["media_class"] == MediaClass.DIRECTORY
    assert item["media_content_type"] == "folder"
    assert item["media_content_id"] == f"{const.URI_SCHEME}{const.DOMAIN}/media"
    assert not item["can_play"]
    assert item["can_expand"]
    assert item["children_media_class"] == MediaClass.MUSIC
    assert len(item["children"]) == 1
    assert item["children"][0]["title"] == "test.mp3"
    assert item["children"][0]["media_class"] == MediaClass.MUSIC


async def test_browse_media_parent_no_children() -> None:
    """Test BrowseMediaSource conversion to media player item dict."""
    base = models.BrowseMediaSource(
        domain=const.DOMAIN,
        identifier="media",
        media_class=MediaClass.DIRECTORY,
        media_content_type="folder",
        title="media/",
        can_play=False,
        can_expand=True,
    )

    item = base.as_dict()
    assert item["title"] == "media/"
    assert item["media_class"] == MediaClass.DIRECTORY
    assert item["media_content_type"] == "folder"
    assert item["media_content_id"] == f"{const.URI_SCHEME}{const.DOMAIN}/media"
    assert not item["can_play"]
    assert item["can_expand"]
    assert len(item["children"]) == 0
    assert item["children_media_class"] is None


async def test_media_source_default_name() -> None:
    """Test MediaSource uses domain as default name."""
    source = models.MediaSource(const.DOMAIN)
    assert source.name == const.DOMAIN


async def test_media_source_item_media_source_id(hass: HomeAssistant) -> None:
    """Test MediaSourceItem media_source_id property."""
    # Test with domain and identifier
    item = models.MediaSourceItem(hass, "test_domain", "test/identifier", None)
    assert item.media_source_id == "media-source://test_domain/test/identifier"

    # Test with domain only
    item = models.MediaSourceItem(hass, "test_domain", "", None)
    assert item.media_source_id == "media-source://test_domain"

    # Test with no domain (root)
    item = models.MediaSourceItem(hass, None, "", None)
    assert item.media_source_id == "media-source://"


async def test_media_source_search_media_not_implemented(hass: HomeAssistant) -> None:
    """Test the base MediaSource.async_search_media raises NotImplementedError."""
    source = models.MediaSource(const.DOMAIN)
    item = models.MediaSourceItem(hass, const.DOMAIN, "", None)
    with pytest.raises(NotImplementedError):
        await source.async_search_media(item, SearchMediaQuery(search_query="test"))


async def test_media_source_item_search_root_aggregates(hass: HomeAssistant) -> None:
    """Test root search aggregates results and skips sources without search."""
    result_item = models.BrowseMediaSource(
        domain="searchable",
        identifier="hit",
        media_class=MediaClass.MUSIC,
        media_content_type=MediaType.MUSIC,
        title="A result",
        can_play=True,
        can_expand=False,
    )

    class SearchableSource(models.MediaSource):
        """A media source that supports search."""

        async def async_search_media(
            self, item: models.MediaSourceItem, query: SearchMediaQuery
        ) -> SearchMedia:
            """Return a fixed result."""
            return SearchMedia(result=[result_item])

    hass.data[MEDIA_SOURCE_DATA] = {
        "searchable": SearchableSource("searchable"),
        "plain": models.MediaSource("plain"),
    }

    item = models.MediaSourceItem(hass, None, "", None)
    result = await item.async_search(SearchMediaQuery(search_query="test"))

    # "plain" does not implement search and is skipped
    assert [entry.title for entry in result.result] == ["A result"]
