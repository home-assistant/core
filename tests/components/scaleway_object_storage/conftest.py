"""Common fixtures for the Scaleway Object Storage tests."""

import asyncio
from collections.abc import Generator, Mapping
from typing import Any, Protocol
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import aiohttp
from aiohttp import ClientResponse
from aiohttp_s3_client import S3Client
from aiohttp_s3_client.client import RequestContextManager
import pytest

from homeassistant.components.backup import AgentBackup
from homeassistant.components.scaleway_object_storage import exceptions
from homeassistant.components.scaleway_object_storage.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.scaleway_object_storage.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def valid_config() -> Mapping[str, Any]:
    """A configuration dict that satisfies the ConfigFlow schema."""
    return {
        CONF_SECTION_CREDENTIALS: {
            CONF_ACCESS_KEY_ID: "SCWSOMETHING",
            CONF_SECRET_KEY: str(uuid.uuid4()),
        },
        CONF_BUCKET: "some-test-bucket",
        CONF_REGION: "fr-par",
        CONF_OBJECT_PREFIX: "prefix/",
    }


@pytest.fixture
def mock_config_entry(valid_config: Mapping[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        # We pretend the user customized the title to ensure the title isn't overwritten by defaults
        title="custom-title",
        domain=DOMAIN,
        data=valid_config,
    )


@pytest.fixture
def mock_config_entry_no_prefix(valid_config: Mapping[str, Any]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config = dict(valid_config)
    config[CONF_OBJECT_PREFIX] = ""
    return MockConfigEntry(
        # We pretend the user customized the title to ensure the title isn't overwritten by defaults
        title="custom-title",
        domain=DOMAIN,
        data=config,
    )


@pytest.fixture
def agent_id(mock_config_entry: MockConfigEntry) -> str:
    """The agent ID for the mock config entry."""
    return f"{DOMAIN}.{mock_config_entry.entry_id}"


@pytest.fixture
def mock_agent_backup() -> AgentBackup:
    """Test backup fixture."""
    return AgentBackup(
        addons=[],
        backup_id="23e64aec",
        date="2024-11-22T11:48:48.727189+01:00",
        database_included=True,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="Core 2024.12.0.dev0",
        protected=False,
        size=1234,
    )


@pytest.fixture
def mock_agent_backup_object_key(
    mock_agent_backup: AgentBackup, valid_config: Mapping[str, Any]
) -> str:
    """The object key for the mock_agent_backup if valid_config is used."""
    prefix = valid_config.get(CONF_OBJECT_PREFIX, "")
    return f"{prefix}home-assistant-backup-{mock_agent_backup.backup_id}.tar"


@pytest.fixture
def mock_read_object_metadata(
    mock_agent_backup: AgentBackup, mock_agent_backup_object_key: str
) -> Generator[AsyncMock]:
    """Mock the helpers.read_object_metadata function to return the mock_agent_backup if requested."""

    async def __read_object_metadata(
        *,
        client: Any,
        object_key: str,
        limiter: asyncio.Semaphore | None,
    ) -> AgentBackup:
        async with limiter or asyncio.Semaphore():
            if object_key == mock_agent_backup_object_key:
                return mock_agent_backup

            raise exceptions.ObjectNotFoundException(object_key=object_key)

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.read_object_metadata",
        side_effect=__read_object_metadata,
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_aiohttp_clientsession() -> Generator[MagicMock]:
    """Mock aiohttp session object returned by hass."""
    mock = MagicMock(spec=aiohttp.ClientSession)
    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=mock,
    ):
        yield mock


@pytest.fixture
def mock_s3_client() -> Generator[MagicMock]:
    """Mock S3 client return by helpers.create_client."""
    mock = MagicMock(spec=S3Client)
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.create_client",
        return_value=mock,
    ):
        yield mock


class MockS3ResponseFactory(Protocol):
    """Factory to create mock S3Client responses."""

    def __call__(self, *, status_code: int) -> tuple[MagicMock, RequestContextManager]:
        """Create a mock aiohttp response and wrap it in a real aiohttp contextmanager.

        It's recommended to assert that the response's release method was called once.

        Args:
            status_code: the status code to set on the response

        Returns:
            a tuple of the mocked ClientResponse and an aiohttp ContextManager that wraps the response.
        """


@pytest.fixture
def mock_s3_response_factory() -> MockS3ResponseFactory:
    """Return a factory function that can be used to create mock aiohttp responses.

    The factory responds with a tuple of the actual ClientResponse mock and the aiohttp
    ContextManager that wraps each response.

    It's recommended to assert that the response's release method was called once.
    """

    def _factory(*, status_code: int) -> tuple[MagicMock, RequestContextManager]:
        response = MagicMock(spec=ClientResponse)
        response.status = status_code
        response.__aenter__.return_value = response
        response.__aexit__.side_effect = response.release

        mock = AsyncMock(return_value=response)
        return response, RequestContextManager(asyncio.ensure_future(mock()))

    return _factory
