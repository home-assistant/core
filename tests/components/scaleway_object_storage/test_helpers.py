"""Tests for helpers module."""

from collections.abc import AsyncGenerator, Mapping
from datetime import UTC, datetime
import json
from typing import Any, cast
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError, ClientResponse, ClientSession, InvalidURL
from aiohttp_s3_client import AwsObjectMeta
from aiohttp_s3_client.client import AwsDownloadError
import pytest

from homeassistant.components.backup import AgentBackup
from homeassistant.components.scaleway_object_storage import exceptions, helpers
from homeassistant.components.scaleway_object_storage.const import (
    CONF_BUCKET,
    CONF_REGION,
    HEADER_METADATA,
)

from .conftest import MockS3ResponseFactory


async def _mock_list_objects() -> AsyncGenerator[tuple[list[AwsObjectMeta], list[Any]]]:
    for key in ("somekey", "someotherkey"):
        meta = AwsObjectMeta(
            etag="cafe",
            key=key,
            last_modified=datetime.now(tz=UTC),
            size=1024,
            storage_class="STANDARD",
        )
        yield [meta], [None]


async def test_list_objects(
    mock_s3_client: MagicMock,
) -> None:
    """Test happy path of list_objects."""
    mock_s3_client.list_objects_v2.return_value = _mock_list_objects()
    keys = [key async for key in helpers.list_objects(client=mock_s3_client, prefix="")]
    assert keys == ["somekey", "someotherkey"]


async def test_list_objects_network_error(
    mock_s3_client: MagicMock,
) -> None:
    """Test network error during list_objects."""
    mock_s3_client.list_objects_v2.side_effect = ClientConnectionError()
    with pytest.raises(exceptions.ScalewayConnectionError):
        async for _ in helpers.list_objects(client=mock_s3_client, prefix=""):
            pass


@pytest.mark.parametrize("status_code", [500, 502, 504])
async def test_list_objects_server_error(
    mock_s3_client: MagicMock,
    status_code: int,
) -> None:
    """Test list_objects with internal server error."""
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = status_code
    mock_s3_client.list_objects_v2.side_effect = AwsDownloadError(
        resp=mock_response, message="An error occurred"
    )

    with pytest.raises(exceptions.ServerUnavailableError):
        async for _ in helpers.list_objects(client=mock_s3_client, prefix=""):
            pass


async def test_list_objects_bucket_not_found(
    mock_s3_client: MagicMock,
) -> None:
    """Test list_objects with non-existent bucket."""
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 404
    mock_s3_client.list_objects_v2.side_effect = AwsDownloadError(
        resp=mock_response, message="An error occurred"
    )

    with pytest.raises(exceptions.BucketNotFoundException):
        async for _ in helpers.list_objects(client=mock_s3_client, prefix=""):
            pass


@pytest.mark.parametrize(
    "status_code",
    [
        401,
        403,
    ],
)
async def test_list_objects_invalid_auth(
    mock_s3_client: MagicMock,
    status_code: int,
) -> None:
    """Test list_objects with invalid credentials."""
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = status_code
    mock_s3_client.list_objects_v2.side_effect = AwsDownloadError(
        resp=mock_response, message="An error occurred"
    )

    with pytest.raises(exceptions.InvalidAuthException):
        async for _ in helpers.list_objects(client=mock_s3_client, prefix=""):
            pass


async def test_read_object_metadata(
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    mock_agent_backup: AgentBackup,
) -> None:
    """Test happy path of read_object_metadata."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_response.headers = {HEADER_METADATA: json.dumps(mock_agent_backup.as_dict())}
    mock_s3_client.head.return_value = mock_response_context

    backup = await helpers.read_object_metadata(
        client=mock_s3_client, object_key="somekey", limiter=None
    )

    assert backup == mock_agent_backup
    assert mock_response.release.call_count == 1


async def test_read_object_metadata_missing_object(
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test read_object_metadata with missing object."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=404)
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.ObjectNotFoundException):
        await helpers.read_object_metadata(
            client=mock_s3_client, object_key="somekey", limiter=None
        )

    assert mock_response.release.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    [
        500,
        502,
        504,
    ],
)
async def test_read_object_metadata_server_error(
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    status_code: int,
) -> None:
    """Test read_object_metadata degraded Scaleway service."""
    mock_response, mock_response_context = mock_s3_response_factory(
        status_code=status_code
    )
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.ServerUnavailableError):
        await helpers.read_object_metadata(
            client=mock_s3_client, object_key="somekey", limiter=None
        )

    assert mock_response.release.call_count == 1


async def test_read_object_metadata_network_error(
    mock_s3_client: MagicMock,
) -> None:
    """Test read_object_metadata with network issues."""
    mock_s3_client.head.side_effect = ClientConnectionError()

    with pytest.raises(exceptions.ScalewayConnectionError):
        await helpers.read_object_metadata(
            client=mock_s3_client, object_key="somekey", limiter=None
        )


async def test_read_object_metadata_invalid_metadata(
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test read_object_metadata with corrupted metadata."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_response.headers = {
        # empty json object
        HEADER_METADATA: "{}"
    }
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.MissingMetadataException):
        await helpers.read_object_metadata(
            client=mock_s3_client, object_key="somekey", limiter=None
        )

    assert mock_response.release.call_count == 1


async def test_read_object_metadata_missing_metadata(
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test read_object_metadata with missing metadata header."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_response.headers = {}
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.MissingMetadataException):
        await helpers.read_object_metadata(
            client=mock_s3_client, object_key="somekey", limiter=None
        )

    assert mock_response.release.call_count == 1


async def test_check_connection(
    mock_aiohttp_clientsession: MagicMock,
    valid_config: Mapping[str, Any],
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test happy path of check_connection."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=200)
    mock_s3_client.head.return_value = mock_response_context

    await helpers.check_connection(
        cast(ClientSession, mock_aiohttp_clientsession), valid_config
    )
    assert mock_response.release.call_count == 1


async def test_check_connection_bucket_not_found(
    mock_aiohttp_clientsession: MagicMock,
    valid_config: Mapping[str, Any],
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test check_connection with non-existent bucket."""
    mock_response, mock_response_context = mock_s3_response_factory(status_code=404)
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.BucketNotFoundException):
        await helpers.check_connection(
            cast(ClientSession, mock_aiohttp_clientsession), valid_config
        )

    assert mock_response.release.call_count == 1


@pytest.mark.parametrize(
    "status_code",
    [
        500,
        502,
        504,
    ],
)
async def test_check_connection_server_error(
    mock_aiohttp_clientsession: MagicMock,
    valid_config: Mapping[str, Any],
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
    status_code: int,
) -> None:
    """Test check_connection if Scaleway service is degraded."""
    mock_response, mock_response_context = mock_s3_response_factory(
        status_code=status_code
    )
    mock_s3_client.head.return_value = mock_response_context

    with pytest.raises(exceptions.ServerUnavailableError):
        await helpers.check_connection(
            cast(ClientSession, mock_aiohttp_clientsession), valid_config
        )

    assert mock_response.release.call_count == 1


async def test_check_connection_invalid_bucket(
    mock_aiohttp_clientsession: MagicMock,
    valid_config: Mapping[str, Any],
    mock_s3_client: MagicMock,
    mock_s3_response_factory: MockS3ResponseFactory,
) -> None:
    """Test check_connection with invalid bucket name."""
    mock_s3_client.head.side_effect = InvalidURL("placeholder")

    config = dict(valid_config)
    config[CONF_BUCKET] = "invalid/bucket&name"

    with pytest.raises(exceptions.InvalidBucketNameException):
        await helpers.check_connection(
            cast(ClientSession, mock_aiohttp_clientsession), config
        )


async def test_check_connection_network_error(
    mock_aiohttp_clientsession: MagicMock,
    valid_config: Mapping[str, Any],
    mock_s3_client: MagicMock,
) -> None:
    """Test check_connection with network error."""
    mock_s3_client.head.side_effect = ClientConnectionError()

    with pytest.raises(exceptions.ScalewayConnectionError):
        await helpers.check_connection(
            cast(ClientSession, mock_aiohttp_clientsession), valid_config
        )


@pytest.mark.parametrize(
    ("bucket_name", "region", "expected_endpoint"),
    [
        ("bucket-name", "fr-par", "https://bucket-name.s3.fr-par.scw.cloud"),
        ("bucket-name", "nl-ams", "https://bucket-name.s3.nl-ams.scw.cloud"),
        ("bucket.with.dots", "fr-par", "https://s3.fr-par.scw.cloud/bucket.with.dots"),
    ],
)
def test_create_client(
    valid_config: Mapping[str, Any],
    mock_aiohttp_clientsession: MagicMock,
    bucket_name: str,
    region: str,
    expected_endpoint: str,
) -> None:
    """Test create_client with different bucket name formats."""
    config = dict(valid_config)
    config[CONF_BUCKET] = bucket_name
    config[CONF_REGION] = region

    client = helpers.create_client(
        cast(ClientSession, mock_aiohttp_clientsession), config
    )
    assert str(client.url) == expected_endpoint


def test_create_client_unscoped(
    valid_config: Mapping[str, Any], mock_aiohttp_clientsession: MagicMock
) -> None:
    """Test create_client with different bucket name formats."""
    client = helpers.create_client(
        cast(ClientSession, mock_aiohttp_clientsession),
        valid_config,
        bucket_scoped=False,
    )
    assert str(client.url) == "https://s3.fr-par.scw.cloud"
