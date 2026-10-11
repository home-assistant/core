"""Compact, bounded Home Assistant views of the typed Koito API models."""

from dataclasses import dataclass

from aiokoito import KoitoData as ApiData, MusicItem as ApiMusicItem, resolve_image_url

MAX_TEXT_LENGTH = 256
MAX_ARTISTS = 20


@dataclass(frozen=True, slots=True)
class Summary:
    """Only the five listening counts exposed by entities."""

    plays: int = 0
    minutes_listened: int = 0
    unique_tracks: int = 0
    unique_albums: int = 0
    unique_artists: int = 0


@dataclass(frozen=True, slots=True)
class MusicItem:
    """Bounded presentation fields for one selected music item."""

    name: str | None = None
    title: str | None = None
    artists: tuple[str, ...] = ()
    image_url: str | None = None
    album_id: int | None = None


@dataclass(frozen=True, slots=True)
class NowPlaying:
    """Availability and optional active track details."""

    currently_playing: bool
    track: MusicItem | None = None


@dataclass(frozen=True, slots=True)
class KoitoData:
    """One refresh with at most one item per ranking and no API metadata."""

    summary: Summary
    top_artist: MusicItem | None = None
    top_album: MusicItem | None = None
    top_track: MusicItem | None = None
    now_playing: NowPlaying | None = None


def _display_text(value: str | None) -> str | None:
    """Bound valid text for entity attributes; protocol validation is upstream."""
    return value.strip()[:MAX_TEXT_LENGTH] if value and value.strip() else None


def _project_item(item: ApiMusicItem | None, base_url: str) -> MusicItem | None:
    if item is None:
        return None
    return MusicItem(
        name=_display_text(item.name),
        title=_display_text(item.title),
        artists=tuple(
            name
            for artist in item.artists[:MAX_ARTISTS]
            if (name := _display_text(artist.name)) is not None
        ),
        image_url=resolve_image_url(item.image, base_url, "medium"),
        album_id=item.album_id,
    )


def project_data(data: ApiData, base_url: str) -> KoitoData:
    """Select only the leading rankings and active playback for Home Assistant."""
    summary = data.summary
    now_playing = data.now_playing
    return KoitoData(
        summary=Summary(
            summary.plays,
            summary.minutes_listened,
            summary.unique_tracks,
            summary.unique_albums,
            summary.unique_artists,
        ),
        top_artist=_project_item(
            summary.top_artists[0].item if summary.top_artists else None, base_url
        ),
        top_album=_project_item(
            summary.top_albums[0].item if summary.top_albums else None, base_url
        ),
        top_track=_project_item(
            summary.top_tracks[0].item if summary.top_tracks else None, base_url
        ),
        now_playing=NowPlaying(
            now_playing.currently_playing,
            _project_item(now_playing.track, base_url)
            if now_playing.currently_playing
            else None,
        )
        if now_playing is not None
        else None,
    )
