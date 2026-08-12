"""Test Music Assistant integration schema helpers."""

from unittest.mock import MagicMock

from music_assistant_models.media_items import Audiobook, MediaItemChapter, Track
from music_assistant_models.media_items.provider_mapping import ProviderMapping

from homeassistant.components.music_assistant.const import ATTR_CHAPTERS
from homeassistant.components.music_assistant.schemas import (
    media_item_dict_from_mass_item,
)


def _provider_mapping() -> ProviderMapping:
    return ProviderMapping(
        item_id="1",
        provider_domain="audiobookshelf",
        provider_instance="audiobookshelf--1234",
    )


def test_media_item_dict_includes_chapters_for_audiobook() -> None:
    """Chapters should be surfaced for audiobooks that have them."""
    mass = MagicMock()
    mass.get_media_item_image_url.return_value = None
    audiobook = Audiobook(
        item_id="1",
        provider="audiobookshelf",
        name="Harry Potter and the Sorcerer's Stone",
        provider_mappings={_provider_mapping()},
    )
    audiobook.metadata.chapters = [
        MediaItemChapter(position=1, name="Chapter 1", start=0.0, end=1756.0),
        MediaItemChapter(position=2, name="Chapter 2", start=1756.0, end=3084.0),
    ]

    result = media_item_dict_from_mass_item(mass, audiobook)

    assert result[ATTR_CHAPTERS] == [
        {"position": 1, "name": "Chapter 1", "start": 0.0, "end": 1756.0},
        {"position": 2, "name": "Chapter 2", "start": 1756.0, "end": 3084.0},
    ]


def test_media_item_dict_omits_chapters_when_none() -> None:
    """No chapters key should be added when the item has none."""
    mass = MagicMock()
    mass.get_media_item_image_url.return_value = None
    audiobook = Audiobook(
        item_id="1",
        provider="audiobookshelf",
        name="Harry Potter and the Sorcerer's Stone",
        provider_mappings={_provider_mapping()},
    )

    result = media_item_dict_from_mass_item(mass, audiobook)

    assert ATTR_CHAPTERS not in result


def test_media_item_dict_omits_chapters_for_non_audiobook_media() -> None:
    """Chapters should not be surfaced for media types other than audiobook, even if the field happens to be populated."""
    mass = MagicMock()
    mass.get_media_item_image_url.return_value = None
    track = Track(
        item_id="1",
        provider="filesystem",
        name="Some Track",
        provider_mappings={
            ProviderMapping(
                item_id="1",
                provider_domain="filesystem",
                provider_instance="filesystem--1234",
            )
        },
    )
    track.metadata.chapters = [
        MediaItemChapter(position=1, name="Chapter 1", start=0.0, end=10.0),
    ]

    result = media_item_dict_from_mass_item(mass, track)

    assert ATTR_CHAPTERS not in result
