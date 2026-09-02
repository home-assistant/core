"""Fixtures for the Community store tests."""

from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
import re
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL

from homeassistant.components.store.base import HacsBase
from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.repositories import (
    HacsAppdaemonRepository,
    HacsIntegrationRepository,
    HacsPluginRepository,
    HacsPythonScriptRepository,
    HacsTemplateRepository,
    HacsThemeRepository,
)
from homeassistant.components.store.repositories.base import HacsRepository
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import dummy_repository_base, get_hacs, setup_integration
from .const import FROZEN_TIME, TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

FIXTURE_PROXY_PATH = Path(__file__).parent / "fixtures" / "proxy"

# GitHub and the data service answer with JSON for paths that carry no
# extension, so the recorded files for those hosts have one appended.
JSON_HOSTS = ("api.github.com", "data-v2.hacs.xyz")

# The recorded responses all came back with a rate limit that never runs out
# and the same etag, which is what the etag bookkeeping is checked against.
PROXY_HEADERS = {
    "Content-Type": "application/json",
    "Etag": "321",
    "X-RateLimit-Limit": "999",
    "X-RateLimit-Remaining": "999",
    "X-RateLimit-Reset": "999",
}


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


class StoreResponses:
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
) -> StoreResponses:
    """Serve the recorded GitHub and data service responses from disk."""
    responses = StoreResponses()
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


@pytest.fixture
def frozen_time(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Move the clock to the instant the recorded responses were made."""
    freezer.move_to(FROZEN_TIME)
    return freezer


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_TOKEN: TOKEN},
        options={"country": "ALL", "appdaemon": True},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.store.async_setup_entry", return_value=True):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the Community store integration for testing."""
    await setup_integration(hass, mock_config_entry)
    yield mock_config_entry
    await hass.config_entries.async_remove(mock_config_entry.entry_id)


@pytest.fixture
def store(hass: HomeAssistant, init_integration: MockConfigEntry) -> HacsBase:
    """Return the store object of a set up integration."""
    return get_hacs(hass)


@pytest.fixture
def mock_repository(store: HacsBase) -> HacsRepository:
    """Return a bare repository."""
    return dummy_repository_base(store)


@pytest.fixture
def mock_repository_appdaemon(store: HacsBase) -> HacsRepository:
    """Return an AppDaemon repository."""
    return dummy_repository_base(store, HacsAppdaemonRepository(store, "test/test"))


@pytest.fixture
def mock_repository_integration(store: HacsBase) -> HacsRepository:
    """Return an integration repository."""
    return dummy_repository_base(store, HacsIntegrationRepository(store, "test/test"))


@pytest.fixture
def mock_repository_plugin(store: HacsBase) -> HacsRepository:
    """Return a dashboard plugin repository."""
    return dummy_repository_base(store, HacsPluginRepository(store, "test/test"))


@pytest.fixture
def mock_repository_python_script(store: HacsBase) -> HacsRepository:
    """Return a python script repository."""
    return dummy_repository_base(store, HacsPythonScriptRepository(store, "test/test"))


@pytest.fixture
def mock_repository_template(store: HacsBase) -> HacsRepository:
    """Return a template repository."""
    return dummy_repository_base(store, HacsTemplateRepository(store, "test/test"))


@pytest.fixture
def mock_repository_theme(store: HacsBase) -> HacsRepository:
    """Return a theme repository."""
    return dummy_repository_base(store, HacsThemeRepository(store, "test/test"))
