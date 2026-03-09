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
    # Group queue items by download ID to handle season packs
    downloads: dict[str, list[Any]] = {}
    for item in queue.records:
        download_id = getattr(item, "downloadId", None)
        if download_id:
            if download_id not in downloads:
                downloads[download_id] = []
            downloads[download_id].append(item)

    shows = {}
    for items in downloads.values():
        if len(items) == 1:
            # Single episode download
            item = items[0]
            shows[item.title] = format_queue_item(item, base_url)
        else:
            # Multiple episodes (season pack) - use first item for main data
            item = items[0]
            formatted = format_queue_item(item, base_url)

            # Get all episode numbers for this download
            episode_numbers = sorted(
                getattr(i.episode, "episodeNumber", 0)
                for i in items
                if hasattr(i, "episode")
            )

            # Format as season pack
            if episode_numbers:
                min_ep = min(episode_numbers)
                max_ep = max(episode_numbers)
                formatted["is_season_pack"] = True
                formatted["episode_count"] = len(episode_numbers)
                formatted["episode_range"] = f"E{min_ep:02d}-E{max_ep:02d}"
                # Update identifier to show it's a season pack
                if formatted.get("season_number") is not None:
                    formatted["episode_identifier"] = (
                        f"S{formatted['season_number']:02d} "
                        f"({len(episode_numbers)} episodes)"
                    )

            shows[item.title] = formatted

    return shows


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
            episode_file_count = getattr(statistics, "episodeFileCount", None)
            episode_count = getattr(statistics, "episodeCount", None)
            formatted_shows[series_title]["episode_file_count"] = episode_file_count
            formatted_shows[series_title]["episode_count"] = episode_count
            # Only format episodes_info if we have valid data
            if episode_file_count is not None and episode_count is not None:
                formatted_shows[series_title]["episodes_info"] = (
                    f"{episode_file_count}/{episode_count} Episodes"
                )
            else:
                formatted_shows[series_title]["episodes_info"] = None

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


# Space unit conversion factors (divisors from bytes)
SPACE_UNITS: dict[str, int] = {
    "bytes": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
    "tb": 1000**4,
    "tib": 1024**4,
    "pb": 1000**5,
    "pib": 1024**5,
}


def format_diskspace(
    disks: list[Diskspace], space_unit: str = "bytes"
) -> dict[str, dict[str, Any]]:
    """Format diskspace for service response.

    Args:
        disks: List of disk space objects from Sonarr.
        space_unit: Unit for space values (bytes, kb, kib, mb, mib, gb, gib, tb, tib, pb, pib).

    Returns:
        Dictionary of disk information keyed by path.
    """
    result = {}
    divisor = SPACE_UNITS.get(space_unit, 1)

    for disk in disks:
        path = disk.path
        free_space = disk.freeSpace / divisor
        total_space = disk.totalSpace / divisor

        result[path] = {
            "path": path,
            "label": getattr(disk, "label", None) or "",
            "free_space": free_space,
            "total_space": total_space,
            "unit": space_unit,
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
        "runtime": getattr(episode, "runtime", None),
        "episode_file_id": getattr(episode, "episodeFileId", None),
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
