"""Integration-internal helper functions that bundle common interactions with the underlying aiohttp_s3_client."""

import asyncio
from http import HTTPStatus
import json
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientConnectionError, ClientSession, InvalidURL
from aiohttp_s3_client import S3Client
from aiohttp_s3_client.client import AwsDownloadError

from homeassistant.components.backup import AgentBackup

from . import exceptions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Mapping

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
    HEADER_METADATA,
)

_LOGGER = logging.getLogger(__name__)


def create_client(
    session: ClientSession,
    config: Mapping[str, Any],
) -> S3Client:
    """Creates a new S3Client that can be used to manipulate objects in a bucket."""
    region = config[CONF_REGION]
    bucket_name = config[CONF_BUCKET]
    if "." in bucket_name:
        # fall back to canonical path addressing to avoid certificate issues
        # see https://www.scaleway.com/en/docs/object-storage/faq/#is-there-a-limitation-in-the-bucket-name
        endpoint_url = f"https://s3.{region}.scw.cloud/{bucket_name}"
    else:
        # virtual-host addressing is generally preferred by S3 API providers because it's easier to
        # scale
        endpoint_url = f"https://{bucket_name}.s3.{region}.scw.cloud"

    credentials = config[CONF_SECTION_CREDENTIALS]

    return S3Client(
        session=session,
        url=endpoint_url,
        access_key_id=credentials[CONF_ACCESS_KEY_ID],
        secret_access_key=credentials[CONF_SECRET_KEY],
        region=region,
    )


def raise_for_status(response_status: int) -> None:
    """If the response_status doesn't indicate success, raise the appropriate ScalewayException.

    Note that 404 responses should best be handled by the caller to get the most specific error for
    the situation (is a bucket or an object missing?).
    """
    try:
        status = HTTPStatus(response_status)
    except ValueError:
        raise exceptions.UnsuccessfulResponseError(response_status) from None

    match status:
        case HTTPStatus.UNAUTHORIZED | HTTPStatus.FORBIDDEN:
            raise exceptions.InvalidAuthException from None
        case status if status.is_server_error:
            raise exceptions.ServerUnavailableError from None
        case status if status.is_success:
            pass
        case other:
            raise exceptions.UnsuccessfulResponseError(other.value) from None


async def check_connection(
    client: S3Client,
) -> None:
    """Attempts to validate config by making a HEAD request to the configured bucket."""
    try:
        response = await client.head(object_name="")
    except ClientConnectionError as e:
        raise exceptions.ScalewayConnectionError from e
    except InvalidURL as e:
        _LOGGER.debug("Invalid URL: %s", e.url, exc_info=e)
        # The bucket is the only part of the URL that's provided by the user,
        # so we assume that an invalid URL must be caused by the bucket name.
        raise exceptions.InvalidBucketNameException from e

    response.release()

    if response.status == HTTPStatus.NOT_FOUND:
        raise exceptions.BucketNotFoundException

    raise_for_status(response.status)


async def read_object_metadata(
    *,
    client: S3Client,
    object_key: str,
    limiter: asyncio.Semaphore | None,
) -> AgentBackup:
    """Read the metadata for a backup object in object storage. Only headers will be requested and no files are downloaded.

    Args:
        client: an S3Client as obtained by create_client()
        object_key: the object key for the backup
        limiter: optional Semaphore to limit concurrent HEAD requests to Scaleway API
    """
    limiter = limiter or asyncio.Semaphore()
    async with limiter:
        _LOGGER.debug("Reading metadata for object %s", object_key)
        try:
            response = await client.head(object_name=object_key)
        except ClientConnectionError as e:
            raise exceptions.ScalewayConnectionError from e

    response.release()

    if response.status == HTTPStatus.NOT_FOUND:
        raise exceptions.ObjectNotFoundException(object_key=object_key)

    raise_for_status(response.status)

    meta = response.headers.get(HEADER_METADATA)
    if meta is None:
        raise exceptions.MissingMetadataException(object_key=object_key)

    try:
        return AgentBackup.from_dict(json.loads(meta))
    except (KeyError, ValueError) as e:
        _LOGGER.warning("Found invalid metadata on object %s", object_key, exc_info=e)
        raise exceptions.MissingMetadataException(object_key=object_key) from None


async def list_objects(*, client: S3Client, prefix: str) -> AsyncGenerator[str]:
    """Lists all object keys in the bucket that match the given prefix."""
    try:
        async for items, _ in client.list_objects_v2(prefix=prefix):
            for meta in items:
                yield meta.key
    except ClientConnectionError as e:
        raise exceptions.ScalewayConnectionError from e
    except AwsDownloadError as e:
        if e.status == HTTPStatus.NOT_FOUND:
            raise exceptions.BucketNotFoundException from None
        raise_for_status(e.status)


def unpack_exception_group[T: Exception](group: ExceptionGroup[T]) -> Generator[T]:
    """Recursively unpacks an ExceptionGroup and yields all individual exceptions contained within."""
    for e in group.exceptions:
        if isinstance(e, ExceptionGroup):
            yield from unpack_exception_group(e)
        else:
            yield e
