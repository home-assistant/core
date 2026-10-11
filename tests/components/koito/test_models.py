"""Test bounded presentation of complete API data."""

from aiokoito import (
    ImageList,
    KoitoData,
    MusicItem,
    NowPlaying,
    RankedItem,
    SimpleArtist,
    Summary,
)

from homeassistant.components.koito.models import project_data


def test_bounded_projection_preserves_artwork() -> None:
    """Select one leader and bound display text, never signed artwork URLs."""
    image = "https://cdn.example/image?signature=" + "a" * 500
    item = MusicItem(
        title="  " + "x" * 500 + "  ",
        artists=tuple(SimpleArtist(name="y" * 500, id=i) for i in range(100)),
        image=ImageList(medium=image),
        listen_count=100,
    )
    summary = Summary(
        plays=42,
        minutes_listened=120,
        unique_tracks=9,
        unique_albums=4,
        unique_artists=3,
        top_albums=(
            RankedItem(rank=1, item=item),
            RankedItem(rank=2, item=MusicItem(title="Other")),
        ),
    )
    result = project_data(
        KoitoData(
            summary=summary,
            now_playing=NowPlaying(currently_playing=True, track=item),
        ),
        "https://koito.example",
    )
    assert result.summary.plays == 42
    assert result.top_album.title == "x" * 256
    assert result.now_playing.track == result.top_album
    assert len(result.top_album.artists) == 20
    assert all(name == "y" * 256 for name in result.top_album.artists)
    assert result.top_album.image_url == image
    assert summary.top_albums[0].item.title == "  " + "x" * 500 + "  "


def test_inactive_playback() -> None:
    """Discard cached track details and whitespace labels from inactive data."""
    result = project_data(
        KoitoData(
            summary=Summary(
                top_artists=(RankedItem(rank=1, item=MusicItem(name="  ")),)
            ),
            now_playing=NowPlaying(
                currently_playing=False, track=MusicItem(title="Stale")
            ),
        ),
        "https://koito.example",
    )
    assert result.top_artist.name is None
    assert result.now_playing.currently_playing is False
    assert result.now_playing.track is None


def test_active_playback_without_track() -> None:
    """A valid active flag does not require cached track metadata."""
    result = project_data(
        KoitoData(summary=Summary(), now_playing=NowPlaying(currently_playing=True)),
        "https://koito.example",
    )
    assert result.now_playing.currently_playing is True
    assert result.now_playing.track is None
