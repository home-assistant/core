"""Helper methods to search for Plex media."""
import logging

from plexapi.exceptions import BadRequest, NotFound

from .errors import MediaNotFound

_LOGGER = logging.getLogger(__name__)


def lookup_movie(library_section, **kwargs):
    """Find a specific movie and return a Plex media object."""
    try:
        title = kwargs["title"]
    except KeyError:
        _LOGGER.error("Must specify 'title' for this search")
        return None

    try:
        movies = library_section.search(**kwargs, libtype="movie", maxresults=3)
    except BadRequest as err:
        _LOGGER.error("Invalid search payload provided: %s", err)
        return None

    if not movies:
        raise MediaNotFound(f"Movie {title}") from None

    if len(movies) > 1:
        exact_matches = [x for x in movies if x.title.lower() == title.lower()]
        if len(exact_matches) == 1:
            return exact_matches[0]
        match_list = [f"{x.title} ({x.year})" for x in movies]
        _LOGGER.warning("Multiple matches found during search: %s", match_list)
        return None

    return movies[0]


def lookup_tv(library_section, **kwargs):
    """Find TV media and return a Plex media object."""
    season_number = kwargs.get("season_number")
    episode_number = kwargs.get("episode_number")

    try:
        show_name = kwargs["show_name"]
        show = library_section.get(show_name)
    except KeyError:
        _LOGGER.error("Must specify 'show_name' for this search")
        return None
    except NotFound as err:
        raise MediaNotFound(f"Show {show_name}") from err

    if not season_number:
        return show

    try:
        season = show.season(int(season_number))
    except NotFound as err:
        raise MediaNotFound(f"Season {season_number} of {show_name}") from err

    if not episode_number:
        return season

    try:
        return season.episode(episode=int(episode_number))
    except NotFound as err:
        episode = f"S{str(season_number).zfill(2)}E{str(episode_number).zfill(2)}"
        raise MediaNotFound(f"Episode {episode} of {show_name}") from err


def lookup_music(library_section, **kwargs):
    """Search for music and return a Plex media object."""
    album_name = kwargs.get("album_name")
    track_name = kwargs.get("track_name")
    track_number = kwargs.get("track_number")

    try:
        artist_name = kwargs["artist_name"]
        artist = library_section.get(artist_name)
    except KeyError:
        _LOGGER.error("Must specify 'artist_name' for this search")
        return None
    except NotFound as err:
        raise MediaNotFound(f"Artist {artist_name}") from err

    if album_name:
        try:
            album = artist.album(album_name)
        except NotFound as err:
            raise MediaNotFound(f"Album {album_name} by {artist_name}") from err

        if track_name:
            try:
                return album.track(track_name)
            except NotFound as err:
                raise MediaNotFound(
                    f"Track {track_name} on {album_name} by {artist_name}"
                ) from err

        if track_number:
            for track in album.tracks():
                if int(track.index) == int(track_number):
                    return track

            raise MediaNotFound(
                f"Track {track_number} on {album_name} by {artist_name}"
            ) from None
        return album

    if track_name:
        try:
            return artist.get(track_name)
        except NotFound as err:
            raise MediaNotFound(f"Track {track_name} by {artist_name}") from err

    return artist
