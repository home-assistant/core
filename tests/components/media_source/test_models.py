"""Test Media Source model methods."""
from homeassistant.components.media_source import const, models


async def test_browse_media_to_media_player_item():
    """Test BrowseMedia conversion to media player item dict."""
    base = models.BrowseMedia(const.DOMAIN, "media", "media/", False, True)
    base.children = [
        models.BrowseMedia(
            const.DOMAIN, "media/test.mp3", "test.mp3", True, False, "audio/mp3"
        )
    ]

    item = base.to_media_player_item()
    assert item["title"] == "media/"
    assert item["media_content_type"] == "folder"
    assert item["media_content_id"] == f"{const.URI_SCHEME}{const.DOMAIN}/media"
    assert not item["can_play"]
    assert item["can_expand"]
    assert len(item["children"]) == 1
    assert item["children"][0]["title"] == "test.mp3"


async def test_media_source_default_name():
    """Test MediaSource uses domain as default name."""
    source = models.MediaSource(const.DOMAIN)
    assert source.name == const.DOMAIN
