"""Tests for the Community store integration."""

from collections import Counter
from collections.abc import Iterable
from http import HTTPStatus
from typing import Any, TypedDict

import pytest
from syrupy.assertion import SnapshotAssertion
from yarl import URL

from homeassistant.components.store.base import HacsBase, async_get_store
from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.enums import HacsCategory
from homeassistant.components.store.repositories.base import (
    HacsManifest,
    HacsRepository,
)
from homeassistant.components.store.utils.logger import LOGGER
from homeassistant.core import HomeAssistant

from .const import PROXY_HEADERS

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


class CategoryTestData(TypedDict):
    """Test data for a single repository category."""

    id: str
    repository: str
    category: str
    files: list[str]
    version_base: str
    version_update: str
    prerelease: str


CATEGORY_TEST_DATA: tuple[CategoryTestData, ...] = (
    CategoryTestData(
        id="1296265",
        category=HacsCategory.APPDAEMON,
        repository="hacs-test-org/appdaemon-basic",
        files=["__init__.py", "example.py"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
    CategoryTestData(
        id="1296269",
        category=HacsCategory.INTEGRATION,
        repository="hacs-test-org/integration-basic",
        files=["__init__.py", "manifest.json", "module/__init__.py"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
    CategoryTestData(
        id="1296267",
        category=HacsCategory.PLUGIN,
        repository="hacs-test-org/plugin-basic",
        files=["example.js", "example.js.gz"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
    CategoryTestData(
        id="1296262",
        category=HacsCategory.PYTHON_SCRIPT,
        repository="hacs-test-org/python_script-basic",
        files=["example.py"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
    CategoryTestData(
        id="1296268",
        category=HacsCategory.TEMPLATE,
        repository="hacs-test-org/template-basic",
        files=["example.jinja"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
    CategoryTestData(
        id="1296266",
        category=HacsCategory.THEME,
        repository="hacs-test-org/theme-basic",
        files=["example.yaml"],
        version_base="1.0.0",
        version_update="2.0.0",
        prerelease="3.0.0",
    ),
)


def category_test_data_parametrized(
    *,
    categories: Iterable[HacsCategory] | None = None,
) -> Iterable[pytest.param]:
    """Return the category test data as pytest parameters."""
    return (
        pytest.param(entry, id=entry["repository"])
        for entry in CATEGORY_TEST_DATA
        if categories is None or entry["category"] in categories
    )


def mocked_response(
    url: str,
    *,
    status: HTTPStatus = HTTPStatus.OK,
    content: bytes | None = None,
    json_content: Any = None,
    headers: dict[str, str] | None = None,
) -> AiohttpClientMockResponse:
    """Return a response to register with the response mocker."""
    return AiohttpClientMockResponse(
        "get",
        URL(url),
        status=status,
        response=content,
        json=json_content,
        headers={**PROXY_HEADERS, **(headers or {})},
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Community store integration."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_hacs(hass: HomeAssistant) -> HacsBase:
    """Return the store object of the loaded config entry."""
    return async_get_store(hass)


def dummy_repository_base(
    hacs: HacsBase, repository: HacsRepository | None = None
) -> HacsRepository:
    """Return a repository with just enough data to be usable in tests."""
    if repository is None:
        repository = HacsRepository(hacs)
        repository.data.full_name = "test/test"
        repository.data.full_name_lower = "test/test"

    repository.hacs = hacs
    repository.hacs.hass = hacs.hass
    repository.hacs.core.config_path = hacs.hass.config.path()
    repository.logger = LOGGER
    repository.data.domain = "test"
    repository.data.last_version = "3"
    repository.data.selected_tag = "3"
    repository.ref = repository.version_to_download()
    repository.integration_manifest = {"config_flow": False, "domain": "test"}
    repository.data.published_tags = ["1", "2", "3"]
    repository.data.update_data(
        load_json_object_fixture("repository_data.json", DOMAIN)
    )
    repository.hacs_manifest = HacsManifest.from_dict({})

    async def update_repository(*args: Any, **kwargs: Any) -> None:
        """Do nothing, the repository data is already set."""

    repository.update_repository = update_repository
    return repository


def api_usage(aioclient_mock: AiohttpClientMocker) -> dict[str, int]:
    """Return the number of requests made per URL, sorted by URL.

    Accidental per-repository round trips to GitHub are the failure mode that
    made HACS slow and rate limited, and a request count is the only thing that
    catches one.
    """
    counted = Counter(str(url) for _, url, _, _ in aioclient_mock.mock_calls)
    return dict(sorted(counted.items()))


def assert_api_usage(
    aioclient_mock: AiohttpClientMocker, snapshot: SnapshotAssertion
) -> None:
    """Assert the recorded request volume matches the snapshot."""
    assert api_usage(aioclient_mock) == snapshot(name="api_usage")
