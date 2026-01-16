"""Helper functions for Radarr."""

from typing import Any

from aiopyarr import RadarrQueue


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
