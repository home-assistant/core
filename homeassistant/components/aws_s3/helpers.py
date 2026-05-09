"""Helpers for the AWS S3 integration."""

from collections.abc import Iterable
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from aiobotocore.client import AioBaseClient as S3Client
from botocore.exceptions import BotoCoreError

from homeassistant.components.backup import AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify
from homeassistant.util.file import WriteError, write_utf8_file

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

METADATA_CACHE_DIR = "backup_metadata"
METADATA_CACHE_SUFFIX = ".json"
METADATA_CACHE_NAME_MAX_LENGTH = 80


def metadata_cache_dir(hass: HomeAssistant, entry_id: str) -> Path:
    """Return the metadata cache directory for a config entry."""
    return Path(hass.config.cache_path(DOMAIN, METADATA_CACHE_DIR, entry_id))


def _metadata_cache_path(cache_dir: Path, metadata_file: dict[str, Any]) -> Path:
    """Return the cache path for a listed S3 metadata object."""
    # ETag is not guaranteed to be a content MD5 for every S3 object, so include
    # other list metadata that changes when the object is replaced.
    metadata_key = str(metadata_file.get("Key", ""))
    identity = "|".join(
        (
            metadata_key,
            str(metadata_file.get("ETag", "")),
            str(metadata_file.get("Size", "")),
            str(metadata_file.get("LastModified", "")),
        )
    )
    readable_name = slugify(Path(metadata_key).name.removesuffix(".metadata.json"))[
        :METADATA_CACHE_NAME_MAX_LENGTH
    ]
    digest = hashlib.blake2s(identity.encode(), digest_size=8).hexdigest()
    return cache_dir / f"{readable_name}_{digest}{METADATA_CACHE_SUFFIX}"


def _read_metadata_cache(cache_path: Path) -> bytes | None:
    """Read metadata bytes from the cache."""
    try:
        if not cache_path.is_file():
            return None
        return cache_path.read_bytes()
    except OSError as err:
        _LOGGER.debug("Failed to read cached metadata file %s: %s", cache_path, err)
        return None


def _write_metadata_cache(cache_path: Path, metadata_content: bytes) -> None:
    """Write metadata bytes to the cache."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_utf8_file(str(cache_path), metadata_content, private=True, mode="wb")
    except (OSError, WriteError) as err:
        _LOGGER.debug("Failed to write cached metadata file %s: %s", cache_path, err)


def _delete_metadata_cache(cache_path: Path) -> None:
    """Delete a metadata cache file."""
    try:
        cache_path.unlink(missing_ok=True)
    except OSError as err:
        _LOGGER.debug("Failed to delete cached metadata file %s: %s", cache_path, err)


def _prune_metadata_cache(cache_dir: Path, used_cache_paths: Iterable[Path]) -> None:
    """Delete cache files that are not part of the latest S3 listing."""
    used_cache_paths = set(used_cache_paths)
    try:
        cache_files = list(cache_dir.glob(f"*{METADATA_CACHE_SUFFIX}"))
    except OSError as err:
        _LOGGER.debug("Failed to list metadata cache directory %s: %s", cache_dir, err)
        return

    for cache_file in cache_files:
        if cache_file in used_cache_paths:
            continue
        _delete_metadata_cache(cache_file)


def _backup_from_metadata_content(
    metadata_content: bytes, metadata_key: str, *, log_warning: bool
) -> AgentBackup | None:
    """Parse backup metadata content."""
    try:
        metadata_json = json.loads(metadata_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        if log_warning:
            _LOGGER.warning(
                "Failed to process metadata file %s: %s",
                metadata_key,
                err,
            )
        return None

    try:
        return AgentBackup.from_dict(metadata_json)
    except (KeyError, TypeError, ValueError) as err:
        if log_warning:
            _LOGGER.warning(
                "Failed to parse metadata in file %s: %s",
                metadata_key,
                err,
            )
        return None


async def _async_download_metadata_content(
    client: S3Client,
    bucket: str,
    metadata_key: str,
) -> bytes | None:
    """Download a metadata file from S3."""
    try:
        metadata_response = await client.get_object(Bucket=bucket, Key=metadata_key)
        return await metadata_response["Body"].read()
    except BotoCoreError as err:
        _LOGGER.warning(
            "Failed to process metadata file %s: %s",
            metadata_key,
            err,
        )
        return None


async def async_list_backups_from_s3(
    hass: HomeAssistant,
    client: S3Client,
    bucket: str,
    prefix: str,
    cache_dir: Path,
) -> list[AgentBackup]:
    """List backups from an S3 bucket by reading metadata files."""
    paginator = client.get_paginator("list_objects_v2")
    metadata_files: list[dict[str, Any]] = []

    list_kwargs: dict[str, Any] = {"Bucket": bucket}
    if prefix:
        list_kwargs["Prefix"] = prefix + "/"

    async for page in paginator.paginate(**list_kwargs):
        metadata_files.extend(
            obj
            for obj in page.get("Contents", [])
            if obj["Key"].endswith(".metadata.json")
        )

    backups: list[AgentBackup] = []
    used_cache_paths: set[Path] = set()
    for metadata_file in metadata_files:
        metadata_key = metadata_file["Key"]
        cache_path = _metadata_cache_path(cache_dir, metadata_file)
        used_cache_paths.add(cache_path)

        metadata_content = await hass.async_add_executor_job(
            _read_metadata_cache, cache_path
        )
        content_from_cache = metadata_content is not None

        if metadata_content is None:
            metadata_content = await _async_download_metadata_content(
                client, bucket, metadata_key
            )
            if metadata_content is None:
                continue

        backup = _backup_from_metadata_content(
            metadata_content, metadata_key, log_warning=not content_from_cache
        )

        if backup is None and content_from_cache:
            # Cached metadata can be safely discarded; S3 remains the source of truth.
            await hass.async_add_executor_job(_delete_metadata_cache, cache_path)
            metadata_content = await _async_download_metadata_content(
                client, bucket, metadata_key
            )
            if metadata_content is None:
                continue
            content_from_cache = False
            backup = _backup_from_metadata_content(
                metadata_content, metadata_key, log_warning=True
            )

        if backup is None:
            continue

        if not content_from_cache:
            await hass.async_add_executor_job(
                _write_metadata_cache, cache_path, metadata_content
            )

        backups.append(backup)

    await hass.async_add_executor_job(
        _prune_metadata_cache, cache_dir, used_cache_paths
    )
    return backups
