"""Helpers for the AWS S3 integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiobotocore.client import AioBaseClient as S3Client
from botocore.exceptions import BotoCoreError

from homeassistant.components.backup import AgentBackup

_LOGGER = logging.getLogger(__name__)


async def async_list_backups_from_s3(
    client: S3Client,
    bucket: str,
) -> list[AgentBackup]:
    """List backups from an S3 bucket by reading metadata files."""
    paginator = client.get_paginator("list_objects_v2")
    metadata_files: list[dict[str, Any]] = []
    async for page in paginator.paginate(Bucket=bucket):
        metadata_files.extend(
            obj
            for obj in page.get("Contents", [])
            if obj["Key"].endswith(".metadata.json")
        )

    backups: list[AgentBackup] = []
    for metadata_file in metadata_files:
        try:
            metadata_response = await client.get_object(
                Bucket=bucket, Key=metadata_file["Key"]
            )
            metadata_content = await metadata_response["Body"].read()
            metadata_json = json.loads(metadata_content)
        except (BotoCoreError, json.JSONDecodeError) as err:
            _LOGGER.warning(
                "Failed to process metadata file %s: %s",
                metadata_file["Key"],
                err,
            )
            continue
        try:
            backup = AgentBackup.from_dict(metadata_json)
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Failed to parse metadata in file %s: %s",
                metadata_file["Key"],
                err,
            )
            continue
        backups.append(backup)

    return backups
