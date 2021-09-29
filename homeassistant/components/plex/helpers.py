"""Helper methods for common Plex integration operations."""


def pretty_title(media, short_name=False):
    """Return a formatted title for the given media item."""
    year = None
    if media.type == "album":
        title = f"{media.parentTitle} - {media.title}"
    elif media.type == "episode":
        title = f"{media.seasonEpisode.upper()} - {media.title}"
        if not short_name:
            title = f"{media.grandparentTitle} - {title}"
    elif media.type == "track":
        title = f"{media.index}. {media.title}"
    else:
        title = media.title

    if media.type in ["album", "movie", "season"]:
        year = media.year

    if year:
        title += f" ({year!s})"

    return title
