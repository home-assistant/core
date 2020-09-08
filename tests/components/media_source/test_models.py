"""Test Media Source model methods."""
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.media_source import const, models


async def test_browse_media_as_dict():
    """Test BrowseMediaSource conversion to media player item dict."""
    base = models.BrowseMediaSource(
        domain=const.DOMAIN,
        identifier="media",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type="folder",
        title="media/",
        can_play=False,
        can_expand=True,
    )
    base.children = [
        models.BrowseMediaSource(
            domain=const.DOMAIN,
            identifier="media/test.mp3",
            media_class=MEDIA_CLASS_MUSIC,
            media_content_type=MEDIA_TYPE_MUSIC,
            title="test.mp3",
            can_play=True,
            can_expand=False,
        )
    ]

    item = base.as_dict()
    assert item["title"] == "media/"
    assert item["media_class"] == MEDIA_CLASS_DIRECTORY
    assert item["media_content_type"] == "folder"
    assert item["media_content_id"] == f"{const.URI_SCHEME}{const.DOMAIN}/media"
    assert not item["can_play"]
    assert item["can_expand"]
    assert len(item["children"]) == 1
    assert item["children"][0]["title"] == "test.mp3"
    assert item["children"][0]["media_class"] == MEDIA_CLASS_MUSIC


async def test_browse_media_parent_no_children():
    """Test BrowseMediaSource conversion to media player item dict."""
    base = models.BrowseMediaSource(
        domain=const.DOMAIN,
        identifier="media",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type="folder",
        title="media/",
        can_play=False,
        can_expand=True,
    )

    item = base.as_dict()
    assert item["title"] == "media/"
    assert item["media_class"] == MEDIA_CLASS_DIRECTORY
    assert item["media_content_type"] == "folder"
    assert item["media_content_id"] == f"{const.URI_SCHEME}{const.DOMAIN}/media"
    assert not item["can_play"]
    assert item["can_expand"]
    assert len(item["children"]) == 0


async def test_media_source_default_name():
    """Test MediaSource uses domain as default name."""
    source = models.MediaSource(const.DOMAIN)
    assert source.name == const.DOMAIN
