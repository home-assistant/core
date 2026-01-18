"""Helper functions for Sonarr."""

import logging
from typing import Any

from aiopyarr import SonarrQueue, SonarrSeries

_LOGGER = logging.getLogger(__name__)


def format_queue_item(item: Any, base_url: str | None = None) -> dict[str, Any]:
    """Format a single queue item."""
    # Calculate progress
    remaining = 1 if item.size == 0 else item.sizeleft / item.size
    remaining_pct = 100 * (1 - remaining)

    result: dict[str, Any] = {
        "id": item.id,
        "series_id": getattr(item, "seriesId", None),
        "episode_id": getattr(item, "episodeId", None),
        "title": item.series.title,
        "download_title": item.title,
        "season_number": getattr(item, "seasonNumber", None),
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
        "episode_has_file": getattr(item, "episodeHasFile", None),
        "estimated_completion_time": str(
            getattr(item, "estimatedCompletionTime", None)
        ),
        "time_left": str(getattr(item, "timeleft", None)),
    }

    # Add episode information from the episode object if available
    if episode := getattr(item, "episode", None):
        result["episode_number"] = getattr(episode, "episodeNumber", None)
        result["episode_title"] = getattr(episode, "title", None)
        # Add formatted identifier like the sensor uses (if we have both season and episode)
        if result["season_number"] is not None and result["episode_number"] is not None:
            result["episode_identifier"] = (
                f"S{result['season_number']:02d}E{result['episode_number']:02d}"
            )

    # Add quality information if available
    if quality := getattr(item, "quality", None):
        result["quality"] = quality.quality.name

    # Add language information if available
    if languages := getattr(item, "languages", None):
        result["languages"] = [lang["name"] for lang in languages]

    # Add custom format score if available
    if custom_format_score := getattr(item, "customFormatScore", None):
        result["custom_format_score"] = custom_format_score

    # Add series images if available
    if images := getattr(item.series, "images", None):
        result["images"] = {}
        for image in images:
            cover_type = image.coverType
            # Prefer remoteUrl (public TVDB URL) over local path
            if remote_url := getattr(image, "remoteUrl", None):
                result["images"][cover_type] = remote_url
            elif base_url and (url := getattr(image, "url", None)):
                result["images"][cover_type] = f"{base_url.rstrip('/')}{url}"

    return result


def format_queue(
    queue: SonarrQueue, base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format queue for service response."""
    shows = {}

    for item in queue.records:
        # Use download_title as key to avoid duplicates when downloading multiple seasons
        shows[item.title] = format_queue_item(item, base_url)

    return shows


def format_episode_item(
    series: SonarrSeries, episode_data: dict[str, Any], base_url: str | None = None
) -> dict[str, Any]:
    """Format a single episode item."""
    result: dict[str, Any] = {
        "id": episode_data.get("id"),
        "episode_number": episode_data.get("episodeNumber"),
        "season_number": episode_data.get("seasonNumber"),
        "title": episode_data.get("title"),
        "air_date": str(episode_data.get("airDate", "")),
        "overview": episode_data.get("overview"),
        "has_file": episode_data.get("hasFile", False),
        "monitored": episode_data.get("monitored", False),
    }

    # Add episode images if available
    if images := episode_data.get("images"):
        result["images"] = {}
        for image in images:
            cover_type = image.coverType
            # Prefer remoteUrl (public TVDB URL) over local path
            if remote_url := getattr(image, "remoteUrl", None):
                result["images"][cover_type] = remote_url
            elif base_url and (url := getattr(image, "url", None)):
                result["images"][cover_type] = f"{base_url.rstrip('/')}{url}"

    return result


def format_series(
    series_list: list[SonarrSeries], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format series list for service response."""
    formatted_shows = {}

    for series in series_list:
        series_title = series.title
        formatted_shows[series_title] = {
            "id": series.id,
            "year": series.year,
            "tvdb_id": getattr(series, "tvdbId", None),
            "imdb_id": getattr(series, "imdbId", None),
            "status": series.status,
            "monitored": series.monitored,
        }

        # Add episode statistics if available (like the sensor shows)
        if statistics := getattr(series, "statistics", None):
            episode_file_count = getattr(statistics, "episodeFileCount", 0)
            episode_count = getattr(statistics, "episodeCount", 0)
            formatted_shows[series_title]["episode_file_count"] = episode_file_count
            formatted_shows[series_title]["episode_count"] = episode_count
            formatted_shows[series_title]["episodes_info"] = (
                f"{episode_file_count}/{episode_count} Episodes"
            )

        # Add series images if available
        if images := getattr(series, "images", None):
            images_dict: dict[str, str] = {}
            for image in images:
                cover_type = image.coverType
                # Prefer remoteUrl (public TVDB URL) over local path
                if remote_url := getattr(image, "remoteUrl", None):
                    images_dict[cover_type] = remote_url
                elif base_url and (url := getattr(image, "url", None)):
                    images_dict[cover_type] = f"{base_url.rstrip('/')}{url}"
            formatted_shows[series_title]["images"] = images_dict

    return formatted_shows
