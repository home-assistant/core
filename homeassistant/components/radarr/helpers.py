"""Helper functions for Radarr."""

from typing import Any

from aiopyarr import RadarrMovie, RadarrQueue


def format_queue_item(item: Any, base_url: str | None = None) -> dict[str, Any]:
    """Format a single queue item."""

    remaining = 1 if item.size == 0 else item.sizeleft / item.size
    remaining_pct = 100 * (1 - remaining)

    movie = item.movie

    result: dict[str, Any] = {
        "id": item.id,
        "movie_id": item.movieId,
        "title": movie["title"],
        "download_title": item.title,
        "progress": f"{remaining_pct:.2f}%",
        "size": item.size,
        "size_left": item.sizeleft,
        "status": item.status,
        "tracked_download_status": getattr(item, "trackedDownloadStatus", None),
        "tracked_download_state": getattr(item, "trackedDownloadState", None),
        "download_client": getattr(item, "downloadClient", None),
        "download_id": getattr(item, "downloadId", None),
        "indexer": getattr(item, "indexer", None),
        "protocol": str(getattr(item, "protocol", None)),
        "estimated_completion_time": str(
            getattr(item, "estimatedCompletionTime", None)
        ),
        "time_left": str(getattr(item, "timeleft", None)),
    }

    if quality := getattr(item, "quality", None):
        result["quality"] = quality.quality.name

    if languages := getattr(item, "languages", None):
        result["languages"] = [lang.name for lang in languages]

    if custom_format_score := getattr(item, "customFormatScore", None):
        result["custom_format_score"] = custom_format_score

    # Add movie images if available
    # Note: item.movie is a dict (not object), so images are also dicts
    if images := movie.get("images"):
        result["images"] = {}
        for image in images:
            cover_type = image.get("coverType")
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
        movies[item.title] = format_queue_item(item, base_url)

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
        "size_on_disk": getattr(movie, "sizeOnDisk", None),
    }

    # Add path if available
    if path := getattr(movie, "path", None):
        result["path"] = path

    # Add movie statistics if available
    if statistics := getattr(movie, "statistics", None):
        result["movie_file_count"] = getattr(statistics, "movieFileCount", None)
        result["size_on_disk"] = getattr(statistics, "sizeOnDisk", None)

    # Add movie images if available
    if images := getattr(movie, "images", None):
        images_dict: dict[str, str] = {}
        for image in images:
            cover_type = image.coverType
            # Prefer remoteUrl (public TMDB URL) over local path
            if remote_url := getattr(image, "remoteUrl", None):
                images_dict[cover_type] = remote_url
            elif base_url and (url := getattr(image, "url", None)):
                images_dict[cover_type] = f"{base_url.rstrip('/')}{url}"
        result["images"] = images_dict

    return result


def format_movies(
    movies: list[RadarrMovie], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format movies list for service response."""
    formatted_movies = {}

    for movie in movies:
        formatted_movies[movie.title] = format_movie_item(movie, base_url)

    return formatted_movies
