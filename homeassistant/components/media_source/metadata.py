"""Helpers for extracting and storing media metadata."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

LOGGER = logging.getLogger(__name__)

META_SUFFIX = ".ha_meta.json"
COVER_SUFFIX = ".ha_cover"


@dataclass(slots=True)
class MediaCover:
    """Represents extracted cover art."""

    data: bytes
    mime_type: str


def is_metadata_sidecar(path: Path) -> bool:
    """Return True if the file is a metadata or cover sidecar."""
    name = path.name
    return name.endswith(META_SUFFIX) or COVER_SUFFIX in name


def metadata_path(path: Path) -> Path:
    """Return the metadata sidecar path for a media file."""
    return path.with_name(f"{path.name}{META_SUFFIX}")


def cover_path(path: Path, extension: str) -> Path:
    """Return the cover sidecar path for a media file."""
    return path.with_name(f"{path.name}{COVER_SUFFIX}{extension}")


def read_metadata(path: Path) -> dict[str, Any] | None:
    """Read metadata sidecar json if it exists."""
    meta_path = metadata_path(path)
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except OSError as err:
        LOGGER.debug("Failed reading metadata for %s: %s", path, err)
    except json.JSONDecodeError as err:
        LOGGER.debug("Invalid metadata json for %s: %s", path, err)
    return None


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Write metadata sidecar json."""
    meta_path = metadata_path(path)
    try:
        meta_path.write_text(json.dumps(metadata, ensure_ascii=True), encoding="utf-8")
    except OSError as err:
        LOGGER.debug("Failed writing metadata for %s: %s", path, err)


def extract_metadata(path: Path) -> tuple[dict[str, Any], MediaCover | None]:
    """Extract metadata and cover art from a media file."""
    metadata: dict[str, Any] = {}
    cover: MediaCover | None = None

    try:
        easy_file = mutagen.File(path, easy=True)
    except mutagen.MutagenError as err:
        LOGGER.debug("Failed to read metadata for %s: %s", path, err)
        easy_file = None

    if easy_file and easy_file.tags:
        metadata.update(_extract_easy_tags(easy_file.tags))

    try:
        full_file = mutagen.File(path)
    except mutagen.MutagenError as err:
        LOGGER.debug("Failed to read metadata for %s: %s", path, err)
        full_file = None

    if full_file and full_file.info and hasattr(full_file.info, "length"):
        metadata["duration"] = int(full_file.info.length)

    if full_file:
        cover = _extract_cover(full_file)

    return metadata, cover


def _extract_easy_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """Extract common tags from mutagen easy tags."""
    result: dict[str, Any] = {}
    mapping = {
        "title": ("title",),
        "artist": ("artist", "albumartist"),
        "album": ("album",),
        "album_artist": ("albumartist",),
        "track_number": ("tracknumber",),
        "disc_number": ("discnumber",),
    }

    for key, sources in mapping.items():
        for source in sources:
            value = tags.get(source)
            if value:
                result[key] = value[0] if isinstance(value, list) else value
                break

    return result


def _extract_cover(file: mutagen.FileType) -> MediaCover | None:
    """Extract cover art from mutagen file types."""
    try:
        if isinstance(file, MP3) and isinstance(file.tags, ID3):
            apic = next(iter(file.tags.getall("APIC")), None)
            if apic and apic.data and apic.mime:
                return MediaCover(apic.data, apic.mime)
        if isinstance(file, FLAC) and file.pictures:
            picture = file.pictures[0]
            if picture.data and picture.mime:
                return MediaCover(picture.data, picture.mime)
        if isinstance(file, MP4) and file.tags:
            cover = file.tags.get("covr")
            if cover:
                cover_item = cover[0]
                if isinstance(cover_item, MP4Cover):
                    mime = (
                        "image/png"
                        if cover_item.imageformat == MP4Cover.FORMAT_PNG
                        else "image/jpeg"
                    )
                    return MediaCover(bytes(cover_item), mime)
    except (AttributeError, mutagen.MutagenError) as err:
        LOGGER.debug("Failed extracting cover art: %s", err)
    return None

