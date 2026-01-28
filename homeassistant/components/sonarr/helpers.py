"""Helper functions for Sonarr."""

from typing import Any

from aiopyarr import (
    Diskspace,
    SonarrCalendar,
    SonarrEpisode,
    SonarrQueue,
    SonarrSeries,
    SonarrWantedMissing,
)


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


def format_diskspace(disks: list[Diskspace]) -> dict[str, dict[str, Any]]:
    """Format diskspace for service response."""
    result = {}

    for disk in disks:
        path = disk.path
        free_bytes = disk.freeSpace
        total_bytes = disk.totalSpace

        # Convert to GB for readability
        free_gb = free_bytes / (1024**3)
        total_gb = total_bytes / (1024**3)
        used_gb = total_gb - free_gb
        usage_pct = (used_gb / total_gb * 100) if total_gb > 0 else 0

        result[path] = {
            "path": path,
            "label": getattr(disk, "label", None) or "",
            "free_space_bytes": free_bytes,
            "total_space_bytes": total_bytes,
            "free_space_gb": round(free_gb, 2),
            "total_space_gb": round(total_gb, 2),
            "used_space_gb": round(used_gb, 2),
            "usage_percent": round(usage_pct, 2),
        }

    return result


def _format_series_images(series: Any, base_url: str | None = None) -> dict[str, str]:
    """Format series images."""
    images_dict: dict[str, str] = {}
    if images := getattr(series, "images", None):
        for image in images:
            cover_type = image.coverType
            # Prefer remoteUrl (public TVDB URL) over local path
            if remote_url := getattr(image, "remoteUrl", None):
                images_dict[cover_type] = remote_url
            elif base_url and (url := getattr(image, "url", None)):
                images_dict[cover_type] = f"{base_url.rstrip('/')}{url}"
    return images_dict


def format_upcoming_item(
    episode: SonarrCalendar, base_url: str | None = None
) -> dict[str, Any]:
    """Format a single upcoming episode item."""
    result: dict[str, Any] = {
        "id": episode.id,
        "series_id": episode.seriesId,
        "season_number": episode.seasonNumber,
        "episode_number": episode.episodeNumber,
        "episode_identifier": f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}",
        "title": episode.title,
        "air_date": str(getattr(episode, "airDate", None)),
        "air_date_utc": str(getattr(episode, "airDateUtc", None)),
        "overview": getattr(episode, "overview", None),
        "has_file": getattr(episode, "hasFile", False),
        "monitored": getattr(episode, "monitored", True),
        "runtime": getattr(episode, "runtime", None),
        "finale_type": getattr(episode, "finaleType", None),
    }

    # Add series information
    if series := getattr(episode, "series", None):
        result["series_title"] = series.title
        result["series_year"] = getattr(series, "year", None)
        result["series_tvdb_id"] = getattr(series, "tvdbId", None)
        result["series_imdb_id"] = getattr(series, "imdbId", None)
        result["series_status"] = getattr(series, "status", None)
        result["network"] = getattr(series, "network", None)
        result["images"] = _format_series_images(series, base_url)

    return result


def format_upcoming(
    calendar: list[SonarrCalendar], base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format upcoming calendar for service response."""
    episodes = {}

    for episode in calendar:
        # Create a unique key combining series title and episode identifier
        series_title = episode.series.title if hasattr(episode, "series") else "Unknown"
        identifier = f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
        key = f"{series_title} {identifier}"
        episodes[key] = format_upcoming_item(episode, base_url)

    return episodes


def format_wanted_item(item: Any, base_url: str | None = None) -> dict[str, Any]:
    """Format a single wanted episode item."""
    result: dict[str, Any] = {
        "id": item.id,
        "series_id": item.seriesId,
        "season_number": item.seasonNumber,
        "episode_number": item.episodeNumber,
        "episode_identifier": f"S{item.seasonNumber:02d}E{item.episodeNumber:02d}",
        "title": item.title,
        "air_date": str(getattr(item, "airDate", None)),
        "air_date_utc": str(getattr(item, "airDateUtc", None)),
        "overview": getattr(item, "overview", None),
        "has_file": getattr(item, "hasFile", False),
        "monitored": getattr(item, "monitored", True),
        "runtime": getattr(item, "runtime", None),
        "tvdb_id": getattr(item, "tvdbId", None),
    }

    # Add series information
    if series := getattr(item, "series", None):
        result["series_title"] = series.title
        result["series_year"] = getattr(series, "year", None)
        result["series_tvdb_id"] = getattr(series, "tvdbId", None)
        result["series_imdb_id"] = getattr(series, "imdbId", None)
        result["series_status"] = getattr(series, "status", None)
        result["network"] = getattr(series, "network", None)
        result["images"] = _format_series_images(series, base_url)

    return result


def format_wanted(
    wanted: SonarrWantedMissing, base_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Format wanted missing episodes for service response."""
    episodes = {}

    for item in wanted.records:
        # Create a unique key combining series title and episode identifier
        series_title = (
            item.series.title if hasattr(item, "series") and item.series else "Unknown"
        )
        identifier = f"S{item.seasonNumber:02d}E{item.episodeNumber:02d}"
        key = f"{series_title} {identifier}"
        episodes[key] = format_wanted_item(item, base_url)

    return episodes


def format_episode(episode: SonarrEpisode) -> dict[str, Any]:
    """Format a single episode from a series."""
    result: dict[str, Any] = {
        "id": episode.id,
        "series_id": episode.seriesId,
        "tvdb_id": getattr(episode, "tvdbId", None),
        "season_number": episode.seasonNumber,
        "episode_number": episode.episodeNumber,
        "episode_identifier": f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}",
        "title": episode.title,
        "air_date": str(getattr(episode, "airDate", None)),
        "air_date_utc": str(getattr(episode, "airDateUtc", None)),
        "has_file": getattr(episode, "hasFile", False),
        "monitored": getattr(episode, "monitored", False),
        "runtime": getattr(episode, "runtime", 0),
        "episode_file_id": getattr(episode, "episodeFileId", 0),
    }

    # Add overview if available (not always present)
    if overview := getattr(episode, "overview", None):
        result["overview"] = overview

    # Add finale type if applicable
    if finale_type := getattr(episode, "finaleType", None):
        result["finale_type"] = finale_type

    return result


def format_episodes(
    episodes: list[SonarrEpisode], season_number: int | None = None
) -> dict[str, dict[str, Any]]:
    """Format episodes list for service response.

    Args:
        episodes: List of episodes to format.
        season_number: Optional season number to filter by.

    Returns:
        Dictionary of episodes keyed by episode identifier (e.g., "S01E01").
    """
    result = {}

    for episode in episodes:
        # Filter by season if specified
        if season_number is not None and episode.seasonNumber != season_number:
            continue

        identifier = f"S{episode.seasonNumber:02d}E{episode.episodeNumber:02d}"
        result[identifier] = format_episode(episode)

    return result
