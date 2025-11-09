"""The tests for the Photo Frame image platform."""

from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource, PlayMedia
from homeassistant.components.photo_frame.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_image(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for source entity device for Photo Frame."""
    freezer.move_to("2025-11-08T12:00:00.000")

    config_entry = MockConfigEntry(
        data={
            "name": "Random Image",
            "media": {
                "media_content_id": "media-source://mymedia",
                "media_content_type": "",
            },
        },
        domain=DOMAIN,
        title="Random Image",
    )

    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            return_value=BrowseMediaSource(
                domain=None,
                identifier=None,
                media_class="",
                media_content_type="",
                title="",
                can_play=False,
                can_expand=True,
                children=[
                    BrowseMedia(
                        media_class=MediaClass.MUSIC,
                        media_content_id="media-source://mymedia/music",
                        media_content_type="audio/mp3",
                        title="a music track",
                        can_play=True,
                        can_expand=False,
                    ),
                    BrowseMedia(
                        media_class=MediaClass.IMAGE,
                        media_content_id="media-source://mymedia/photo",
                        media_content_type="image/png",
                        title="a picture",
                        can_play=True,
                        can_expand=False,
                    ),
                ],
            ),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=PlayMedia(
                url="fake", mime_type="png", path=Path("/local/whatever")
            ),
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("image.random_image")

    assert state and state.state == "2025-11-08T12:00:00+00:00"
