"""Helper functions for Radarr."""

from typing import Any

from aiopyarr import RadarrMovie, RadarrQueue


def format_queue_item(item: Any, base_url: str | None = None) -> dict[str, Any]:
    """Format a single queue item."""
    # Calculate progress
    remaining = 1 if item.size == 0 else item.sizeleft / item.size
    remaining_pct = 100 * (1 - remaining)

    # Get movie title with fallback to download title
    movie_title = getattr(item, "movie", {}).get("title", item.title)

    result: dict[str, Any] = {
        "id": item.id,
        "movie_id": item.movieId,
        "title": movie_title,
        "download_title": item.title,
        "progress": f"{remaining_pct:.2f}%",
        "size": item.size,
        "size_left": item.sizeleft,
        "status": item.status,
        "tracked_download_status": getattr(item, "trackedDownloadStatus", None),
        "tracked_download_state": getattr(item, "trackedDownloadState", None),
        "download_client": getattr(item, "downloadClient", None),
        "indexer": getattr(item, "indexer", None),
        "protocol": str(getattr(item, "protocol", None)),
    }

    # Add movie images if available
    if movie := getattr(item, "movie", None):
        if images := movie.get("images"):
            result["images"] = {}
            for image in images:
                cover_type = image.get("coverType")
                if not cover_type:
                    continue

                # Prefer remoteUrl (public TMDB URL) over local path
                if remote_url := image.get("remoteUrl"):
                    result["images"][cover_type] = remote_url
                elif base_url and (url := image.get("url")):
                    result["images"][cover_type] = f"{base_url.rstrip('/')}{url}"

    return result


def format_queue(
    queue: RadarrQueue, base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format queue for service response."""
    movies = {}

    for item in queue.records:
        # Get movie title with fallback
        movie_title = getattr(item, "movie", {}).get("title", item.title)
        movies[movie_title] = format_queue_item(item, base_url)

    return movies


def format_movie_item(
    movie: RadarrMovie, base_url: str | None = None
) -> dict[str, Any]:
    """Format a single movie item."""
    result: dict[str, Any] = {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "tmdb_id": movie.tmdbId,
        "imdb_id": getattr(movie, "imdbId", None),
        "status": movie.status,
        "monitored": movie.monitored,
        "has_file": movie.hasFile,
        "size_on_disk": getattr(movie, "sizeOnDisk", 0),
    }

    # Add path if available
    if path := getattr(movie, "path", None):
        result["path"] = path

    # Add movie statistics if available
    if statistics := getattr(movie, "statistics", None):
        result["movie_file_count"] = getattr(statistics, "movieFileCount", 0)
        result["size_on_disk"] = getattr(statistics, "sizeOnDisk", 0)

    # Add movie images if available
    if images := getattr(movie, "images", None):
        result["images"] = {}
        for image in images:
            # Handle both dict and object types
            if isinstance(image, dict):
                cover_type = image.get("coverType")
                remote_url = image.get("remoteUrl")
                url = image.get("url")
            else:
                cover_type = getattr(image, "coverType", None)
                remote_url = getattr(image, "remoteUrl", None)
                url = getattr(image, "url", None)

            if not cover_type:
                continue

            # Prefer remoteUrl (public TMDB URL) over local path
            if remote_url:
                result["images"][cover_type] = remote_url
            elif base_url and url:
                result["images"][cover_type] = f"{base_url.rstrip('/')}{url}"

    return result


def format_movies(
    movies: list[RadarrMovie], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format movies list for service response."""
    formatted_movies = {}

    for movie in movies:
        formatted_movies[movie.title] = format_movie_item(movie, base_url)

    return formatted_movies
