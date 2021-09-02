"""Tests for media search utilities."""

from homeassistant.components.media_player.const import MEDIA_TYPE_EPISODE
from homeassistant.components.plex.const import DOMAIN, SERVERS
from homeassistant.components.plex.media_search import continue_media


async def test_media_continuation(hass, mock_plex_server):
    """Test media continuation of looked up Plex media."""
    server_id = mock_plex_server.machine_identifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Testing is done in two consecutive stages: first we extract, process and
    # validate server responses (show, season, episode), then we use these
    # responses as test targets for the continue_media method tests

    # Show test targets
    show = loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE, library_name="TV Shows", show_name="TV Show"
    )
    assert show is not None

    show_episodes = show.episodes()
    assert show_episodes is not None
    assert len(show_episodes) > 5

    show_first = show_episodes[0]
    assert show_first is not None

    show_ondeck = show.onDeck()
    assert show_ondeck is not None
    assert (
        show_ondeck != show_first
    )  # we don't want the test to be indistinguishable from a documented edge case

    show_unfinished_first = next(
        iter(e for e in show_episodes if e.viewOffset), show_first
    )
    assert show_unfinished_first is not None

    show_unfinished_last = next(
        iter(e for e in reversed(show_episodes) if e.viewOffset), show_first
    )
    assert show_unfinished_last is not None

    show_unfinished_first = next(
        iter(e for e in show_episodes if e.viewOffset), show_first
    )
    assert show_unfinished_first is not None

    show_unfinished_last = next(
        iter(e for e in reversed(show.episodes()) if e.viewOffset), show_first
    )
    assert show_unfinished_last is not None

    show_unwatched_first = next(iter(show.unwatched()), show_first)
    assert show_unwatched_first is not None

    show_unwatched_last = next(iter(reversed(show.unwatched())), show_first)
    assert show_unwatched_last is not None

    show_watched_first = next(iter(show.watched()), show_first)
    assert show_watched_first is not None

    show_watched_last = next(iter(reversed(show.watched())), show_first)
    assert show_watched_last is not None

    # Season test targets
    # Note: Season gets extra validation to avoid ambiguity in test data, and since this is
    # the only season in the show - the benefit will be shared by both media types
    season = loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="TV Show",
        season_number=1,
    )
    assert season is not None

    season_episodes = season.episodes()
    assert season_episodes is not None
    assert len(season_episodes) > 5

    season_first = season_episodes[0]
    assert season_first is not None

    season_ondeck = season.onDeck()
    assert season_ondeck is not None

    season_unfinished_first = next(
        iter(e for e in season_episodes if e.viewOffset), season
    )
    assert season_unfinished_first is not None
    assert season_unfinished_first != season
    assert season_unfinished_first != season_first

    season_unfinished_last = next(
        iter(e for e in reversed(season_episodes) if e.viewOffset), season
    )
    assert season_unfinished_last is not None
    assert season_unfinished_last != season
    assert season_unfinished_last != season_first

    season_unwatched_first = next(iter(season.unwatched()), season)
    assert season_unwatched_first is not None
    assert season_unwatched_first != season
    assert season_unwatched_first != season_first

    season_unwatched_last = next(iter(reversed(season.unwatched())), season)
    assert season_unwatched_last is not None
    assert season_unwatched_last != season
    assert season_unwatched_last != season_first

    season_watched_first = next(iter(season.watched()), season)
    assert season_watched_first is not None
    assert season_watched_first != season

    season_watched_last = next(iter(reversed(season.watched())), season)
    assert season_watched_last is not None
    assert season_watched_last != season
    assert season_watched_last != season_first

    # Episode test target - episodes are not supported, this test may as well be any other unsupported media type
    episode = loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="TV Show",
        season_number=1,
        episode_number=3,
    )
    assert episode is not None
    assert episode != show_first

    # Beginning method testing using the test targets acquired earlier

    # Testing ondeck continuation mode
    assert continue_media(show, "ondeck") == show_ondeck
    assert continue_media(season, "ondeck") == season_ondeck
    assert continue_media(episode, "ondeck") == episode

    # Testing unfinished continuation mode
    assert continue_media(show, "unfinished") == show_unfinished_first
    assert continue_media(season, "unfinished") == season_unfinished_first
    assert continue_media(episode, "unfinished") == episode

    assert continue_media(show, "unfinished_first") == show_unfinished_first
    assert continue_media(season, "unfinished_first") == season_unfinished_first
    assert continue_media(episode, "unfinished_first") == episode

    assert continue_media(show, "unfinished_last") == show_unfinished_last
    assert continue_media(season, "unfinished_last") == season_unfinished_last
    assert continue_media(episode, "unfinished_last") == episode

    # Testing unwatched continuation mode
    assert continue_media(show, "unwatched") == show_unwatched_first
    assert continue_media(season, "unwatched") == season_unwatched_first
    assert continue_media(episode, "unwatched") == episode

    assert continue_media(show, "unwatched_first") == show_unwatched_first
    assert continue_media(season, "unwatched_first") == season_unwatched_first
    assert continue_media(episode, "unwatched_first") == episode

    assert continue_media(show, "unwatched_last") == show_unwatched_last
    assert continue_media(season, "unwatched_last") == season_unwatched_last
    assert continue_media(episode, "unwatched_last") == episode

    # Testing watched continuation mode
    assert continue_media(show, "watched") == show_watched_first
    assert continue_media(season, "watched") == season_watched_first
    assert continue_media(episode, "watched") == episode

    assert continue_media(show, "watched_first") == show_watched_first
    assert continue_media(season, "watched_first") == season_watched_first
    assert continue_media(episode, "watched_first") == episode

    assert continue_media(show, "watched_last") == show_watched_last
    assert continue_media(season, "watched_last") == season_watched_last
    assert continue_media(episode, "watched_last") == episode

    # Testing fallback logic
    assert continue_media(show, "|ondeck") == show_ondeck
    assert continue_media(season, "|ondeck") == season_ondeck

    # Testing valid mode with poorly formatted but valid arguments
    assert continue_media(season, "unfinished____first") == season_unfinished_first
    assert continue_media(season, "unfinished____last") == season_unfinished_last

    # Testing valid mode with multiple valid conflicting consecutive arguments
    assert continue_media(season, "unfinished_last_first") == season_unfinished_first
    assert continue_media(season, "unfinished_first_last") == season_unfinished_last

    # Testing invalid arguments
    assert continue_media(show, "") == show
    assert continue_media(season, "") == season
    assert continue_media(season, "invalid-mode") == season
    assert continue_media(season, "invalid-mode_invalid_args") == season
    assert continue_media(season, "|a|") == season
    assert continue_media(season, "||") == season
    assert continue_media(season, "|_|") == season
    assert continue_media(season, "_first") == season
    assert continue_media(season, "_last") == season
    assert continue_media(season, "|___last|") == season
