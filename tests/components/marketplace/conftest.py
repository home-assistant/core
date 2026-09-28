"""Fixtures for the Marketplace tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch

from aiogithubapi import GitHubLoginDeviceModel, GitHubLoginOauthModel
from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.auth.models import User
from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    STORAGE_VERSION,
)
from homeassistant.components.marketplace.repositories import (
    IntegrationRepository,
    PluginRepository,
    TemplateRepository,
    ThemeRepository,
)
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import (
    create_download_folders,
    dummy_repository_base,
    get_marketplace,
    setup_integration,
)
from .const import FROZEN_TIME, PROXY_HEADERS, TOKEN, WARNING_ACCEPTANCE

from tests.common import (
    CLIENT_ID,
    MockConfigEntry,
    MockUser,
    async_load_json_object_fixture,
    load_json_object_fixture,
)
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

FIXTURE_PROXY_PATH = Path(__file__).parent / "fixtures" / "proxy"

# GitHub and the data service answer with JSON for paths that carry no
# extension, so the recorded files for those hosts have one appended.
JSON_HOSTS = ("api.github.com", "data-v2.hacs.xyz")


@lru_cache
def _load_proxy_fixtures() -> dict[str, bytes]:
    """Read every recorded response from disk, keyed by host and path."""
    return {
        path.relative_to(FIXTURE_PROXY_PATH).as_posix(): path.read_bytes()
        for path in FIXTURE_PROXY_PATH.rglob("*")
        if path.is_file()
    }


def _fixture_key(url: URL) -> str:
    """Return the recorded response a request URL maps to.

    Query strings are ignored, the recordings are keyed by path alone.
    """
    key = f"{url.host}{url.path}"
    if url.host in JSON_HOSTS and not url.path.endswith(".json"):
        return f"{key}.json"
    return key


class MarketplaceResponses:
    """Responses that take precedence over the recorded ones."""

    def __init__(self) -> None:
        """Initialize the overrides."""
        self._responses: dict[str, tuple[AiohttpClientMockResponse, bool]] = {}

    def add(
        self,
        url: str,
        response: AiohttpClientMockResponse,
        *,
        keep: bool = False,
    ) -> None:
        """Register a response to serve instead of the recorded one.

        The response is served once unless keep is set, so a test can queue a
        single answer and let the requests after it fall back to the recording.
        """
        self._responses[url] = (response, keep)

    def pop(self, url: str) -> AiohttpClientMockResponse | None:
        """Return the override registered for the URL, if there is one."""
        if (entry := self._responses.get(url)) is None:
            return None

        response, keep = entry
        if not keep:
            del self._responses[url]
        return response


@pytest.fixture(autouse=True)
async def response_mocker(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> MarketplaceResponses:
    """Serve the recorded GitHub and data service responses from disk."""
    responses = MarketplaceResponses()
    fixtures = await hass.async_add_executor_job(_load_proxy_fixtures)

    async def _serve(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        """Answer a request from the overrides or from the recordings."""
        if (override := responses.pop(str(url))) is not None:
            return override

        if (body := fixtures.get(_fixture_key(url))) is None:
            return AiohttpClientMockResponse(
                method, url, status=HTTPStatus.NOT_FOUND, headers=PROXY_HEADERS
            )

        return AiohttpClientMockResponse(
            method, url, response=body, headers=PROXY_HEADERS
        )

    for method in ("get", "head", "post"):
        aioclient_mock.request(method, re.compile(r".*"), side_effect=_serve)

    return responses


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Point the configuration directory at a temporary one.

    The Marketplace writes downloads straight into the configuration directory, so
    it has to be a throwaway one rather than the shared test configuration.
    """
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture
def device_activation_event() -> asyncio.Event:
    """Return the event that releases the mocked device activation."""
    return asyncio.Event()


@pytest.fixture
def github_device_client(
    hass: HomeAssistant, device_activation_event: asyncio.Event
) -> Generator[AsyncMock]:
    """Mock the GitHub device flow client used by the config flow."""
    with patch(
        "homeassistant.components.marketplace.config_flow.GitHubDeviceAPI",
        autospec=True,
    ) as device_client_mock:
        client = device_client_mock.return_value

        registration = AsyncMock()
        registration.data = GitHubLoginDeviceModel(
            load_json_object_fixture("device_register.json", DOMAIN)
        )
        client.register.return_value = registration

        async def mock_activation(device_code: str) -> AsyncMock:
            """Wait for the test to release the activation, then return."""
            await device_activation_event.wait()
            activation = AsyncMock()
            activation.data = GitHubLoginOauthModel(
                await async_load_json_object_fixture(
                    hass, "device_activate.json", DOMAIN
                )
            )
            return activation

        client.activation = mock_activation
        yield client


@pytest.fixture
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Move the clock to the instant the recorded responses were made."""
    freezer.move_to(FROZEN_TIME)
    return freezer


@pytest.fixture
def github_token() -> str | None:
    """Return the token of the connected GitHub account, None for no account."""
    return TOKEN


@pytest.fixture
def warning_accepted(hass_admin_user: MockUser) -> dict[str, Any] | None:
    """Return the stored acceptances of the first-run warning, None for none."""
    return {hass_admin_user.id: WARNING_ACCEPTANCE}


@pytest.fixture
async def second_admin_user(hass: HomeAssistant) -> User:
    """Return a second admin, who has not accepted the warning."""
    return await hass.auth.async_create_user("Second admin", group_ids=[GROUP_ID_ADMIN])


@pytest.fixture
async def second_admin_token(hass: HomeAssistant, second_admin_user: User) -> str:
    """Return an access token of the second admin."""
    refresh_token = await hass.auth.async_create_refresh_token(
        second_admin_user, CLIENT_ID
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def config_entry_source() -> str:
    """Return how the config entry was created."""
    return SOURCE_USER


@pytest.fixture
def mock_config_entry(
    github_token: str | None,
    warning_accepted: dict[str, Any] | None,
    config_entry_source: str,
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    data: dict[str, Any] = {}
    if github_token:
        data[CONF_TOKEN] = github_token
    if warning_accepted:
        data[CONF_WARNING_ACCEPTED] = warning_accepted

    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        source=config_entry_source,
        data=data,
        unique_id="12345",
    )


@pytest.fixture
def stored_repositories(hass_storage: dict[str, Any], config_dir: Path) -> None:
    """Seed the stored repositories with two downloaded repositories."""
    repositories = load_json_object_fixture("stored_repositories.json", DOMAIN)
    hass_storage[f"{DOMAIN}.repositories"] = {
        "version": STORAGE_VERSION,
        "data": repositories,
    }
    create_download_folders(config_dir, repositories)


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.marketplace.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the Marketplace integration for testing."""
    await setup_integration(hass, mock_config_entry)
    yield mock_config_entry
    await hass.config_entries.async_remove(mock_config_entry.entry_id)


@pytest.fixture
def marketplace(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> MarketplaceManager:
    """Return the Marketplace object of a set up integration."""
    return get_marketplace(hass)


@pytest.fixture
def mock_repository(marketplace: MarketplaceManager) -> Repository:
    """Return a bare repository."""
    return dummy_repository_base(marketplace)


@pytest.fixture
def mock_repository_integration(marketplace: MarketplaceManager) -> Repository:
    """Return an integration repository."""
    return dummy_repository_base(
        marketplace, IntegrationRepository(marketplace, "test/test")
    )


@pytest.fixture
def mock_repository_plugin(marketplace: MarketplaceManager) -> Repository:
    """Return a dashboard plugin repository."""
    return dummy_repository_base(
        marketplace, PluginRepository(marketplace, "test/test")
    )


@pytest.fixture
def mock_repository_template(marketplace: MarketplaceManager) -> Repository:
    """Return a template repository."""
    return dummy_repository_base(
        marketplace, TemplateRepository(marketplace, "test/test")
    )


@pytest.fixture
def mock_repository_theme(marketplace: MarketplaceManager) -> Repository:
    """Return a theme repository."""
    return dummy_repository_base(marketplace, ThemeRepository(marketplace, "test/test"))
