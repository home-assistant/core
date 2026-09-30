"""Tests for the Marketplace data client."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.enums import (
    MarketplaceStage,
    RepositoryCategory,
)
from homeassistant.components.marketplace.exceptions import (
    MarketplaceError,
    NotModifiedError,
)
from homeassistant.core import HomeAssistant

from . import (
    CategoryTestData,
    category_test_data_parametrized,
    get_marketplace,
    mocked_response,
)
from .conftest import MarketplaceResponses
from .const import PROXY_HEADERS, REPOSITORY_PLUGIN_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse

GOOD_COMMON_DATA = {
    "description": "abc",
    "etag_repository": "blah",
    "full_name": "blah",
    "last_commit": "abc",
    "last_fetched": 0,
    "last_updated": "blah",
    "manifest": {},
}

GOOD_INTEGRATION_DATA = GOOD_COMMON_DATA | {"domain": "abc", "manifest_name": "abc"}


def _without_description(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the data with the required description removed."""
    return {key: value for key, value in data.items() if key != "description"}


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_get_data(
    marketplace: MarketplaceManager,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the repository data of every category."""
    result = await marketplace.data_client.get_data(
        category_test_data["category"], validate=True
    )

    assert result == snapshot


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_get_repositories(
    marketplace: MarketplaceManager,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the repository list of every category."""
    result = await marketplace.data_client.get_repositories(
        category_test_data["category"]
    )

    assert result == snapshot


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        pytest.param(
            Exception("Test"),
            "Error fetching data from the catalog: Test",
            id="exception",
        ),
        pytest.param(TimeoutError, "Timeout of 60s reached", id="timeout"),
    ],
)
async def test_request_exceptions(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    exception: Exception,
    message: str,
) -> None:
    """Test the errors a failing request is reported as."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    response_mocker.add(
        url, AiohttpClientMockResponse("get", url, exc=exception), keep=True
    )

    with pytest.raises(MarketplaceError, match=message):
        await marketplace.data_client.get_repositories("integration")


async def test_catalog_larger_than_the_limit(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a catalog response that is too large is not read into memory."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    response_mocker.add(url, mocked_response(url, content=b'["' + b"0" * 20 + b'"]'))

    with (
        patch(
            "homeassistant.components.marketplace.utils.response.MAX_DOWNLOAD_SIZE", 10
        ),
        pytest.raises(MarketplaceError, match="larger than the 10 byte limit"),
    ):
        await marketplace.data_client.get_repositories("integration")


@pytest.mark.parametrize(
    ("status", "expectation"),
    [
        pytest.param(HTTPStatus.OK, does_not_raise(), id="200"),
        pytest.param(HTTPStatus.CREATED, does_not_raise(), id="201"),
        pytest.param(
            HTTPStatus.NOT_MODIFIED,
            pytest.raises(NotModifiedError),
            id="304",
        ),
        pytest.param(HTTPStatus.BAD_REQUEST, pytest.raises(MarketplaceError), id="400"),
        pytest.param(
            HTTPStatus.UNAUTHORIZED, pytest.raises(MarketplaceError), id="401"
        ),
        pytest.param(HTTPStatus.FORBIDDEN, pytest.raises(MarketplaceError), id="403"),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS, pytest.raises(MarketplaceError), id="429"
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            pytest.raises(MarketplaceError),
            id="500",
        ),
    ],
)
async def test_request_status_handling(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    status: HTTPStatus,
    expectation: AbstractContextManager[Any],
) -> None:
    """Test which response status codes are treated as an error."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    response_mocker.add(
        url, mocked_response(url, status=status, json_content=[]), keep=True
    )

    with expectation:
        await marketplace.data_client.get_repositories("integration")


async def test_etag_is_sent_back(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the etag of a response is used for the next request."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    await marketplace.data_client.get_repositories("integration")

    response_mocker.add(
        url, mocked_response(url, status=HTTPStatus.NOT_MODIFIED), keep=True
    )

    with pytest.raises(NotModifiedError):
        await marketplace.data_client.get_repositories("integration")

    # The mocked answer is a 304 anyway, the header is what saves the download
    assert aioclient_mock.mock_calls[-1][3]["If-None-Match"] == PROXY_HEADERS["Etag"]


@pytest.mark.parametrize(
    ("section", "data"),
    [
        pytest.param(
            "integration",
            {"12345": _without_description(GOOD_INTEGRATION_DATA)},
            id="integration",
        ),
        pytest.param(
            "plugin", {"12345": _without_description(GOOD_COMMON_DATA)}, id="plugin"
        ),
        pytest.param(
            "template",
            {"12345": _without_description(GOOD_COMMON_DATA)},
            id="template",
        ),
        pytest.param(
            "theme", {"12345": _without_description(GOOD_COMMON_DATA)}, id="theme"
        ),
        pytest.param(
            "critical", [{"repository": "test", "reason": "blah"}], id="critical"
        ),
        pytest.param("removed", [{"repository": "test"}], id="removed"),
    ],
)
async def test_invalid_data_is_discarded(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    section: str,
    data: dict[str, Any] | list[Any],
) -> None:
    """Test that invalid data is dropped when validation is on, and kept when off."""
    url = f"https://data-v2.hacs.xyz/{section}/data.json"

    response_mocker.add(url, mocked_response(url, json_content=data))
    assert await marketplace.data_client.get_data(section, validate=True) in ({}, [])

    response_mocker.add(url, mocked_response(url, json_content=data))
    assert await marketplace.data_client.get_data(section, validate=False) == data


async def test_unknown_section_can_not_be_validated(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test that a section without a schema is refused."""
    url = "https://data-v2.hacs.xyz/unknown/data.json"
    response_mocker.add(url, mocked_response(url, json_content=[]))

    with pytest.raises(ValueError, match="Do not know how to validate unknown"):
        await marketplace.data_client.get_data("unknown", validate=True)


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_invalid_repository_data_is_not_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    response_mocker: MarketplaceResponses,
    category_test_data: CategoryTestData,
) -> None:
    """Test that a repository with invalid data is skipped during setup."""
    url = f"https://data-v2.hacs.xyz/{category_test_data['category']}/data.json"
    response_mocker.add(
        url,
        mocked_response(
            url,
            json_content={
                category_test_data["id"]: _without_description(GOOD_COMMON_DATA)
            },
        ),
        keep=True,
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    marketplace = get_marketplace(hass)
    assert not marketplace.system.disabled
    assert marketplace.stage == "running"
    assert (
        marketplace.repositories.get_by_full_name(category_test_data["repository"])
        is None
    )


@pytest.mark.parametrize(
    ("section", "content"),
    [
        pytest.param("integration", b"{not json", id="not_json"),
        pytest.param("integration", b'["a list"]', id="list_for_repositories"),
        pytest.param("critical", b'{"an": "object"}', id="object_for_critical"),
        pytest.param("removed", b"42", id="number_for_removed"),
    ],
)
async def test_malformed_catalog_is_a_catalog_error(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    section: str,
    content: bytes,
) -> None:
    """Test a broken catalog answer is refused like any failed request."""
    url = f"https://data-v2.hacs.xyz/{section}/data.json"
    response_mocker.add(url, mocked_response(url, content=content))

    with pytest.raises(MarketplaceError):
        await marketplace.data_client.get_data(section, validate=True)


async def test_malformed_catalog_is_fetched_again(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the etag of a broken answer is not kept, the next request gets data."""
    etag = marketplace.data_client._etags.get("integration/data.json")
    url = "https://data-v2.hacs.xyz/integration/data.json"
    response_mocker.add(
        url, mocked_response(url, content=b"{not json", headers={"etag": "broken"})
    )

    with pytest.raises(MarketplaceError):
        await marketplace.data_client.get_data("integration", validate=True)

    assert marketplace.data_client._etags.get("integration/data.json") == etag


async def test_catalog_entry_that_is_not_an_object_is_skipped(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test one broken entry does not take the rest of the category down."""
    url = "https://data-v2.hacs.xyz/integration/data.json"
    response_mocker.add(url, mocked_response(url, json_content={"1": "broken"}))

    assert await marketplace.data_client.get_data("integration", validate=True) == {}


async def test_catalog_entry_without_a_numeric_id_is_skipped(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a catalog key that is not a GitHub repository id is dropped."""
    data = GOOD_INTEGRATION_DATA | {"full_name": "owner/blah"}
    url = "https://data-v2.hacs.xyz/integration/data.json"
    response_mocker.add(
        url,
        mocked_response(
            url, json_content={"../1": data, "-1": data, "١": data, "1": data}
        ),
    )

    assert await marketplace.data_client.get_data("integration", validate=True) == {
        "1": data
    }


@pytest.mark.parametrize(
    "catalog",
    [
        pytest.param({}, id="empty"),
        pytest.param({REPOSITORY_PLUGIN_ID: {"full_name": 1}}, id="nothing_valid"),
    ],
)
async def test_empty_catalog_at_startup_keeps_the_category(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    catalog: dict[str, Any],
) -> None:
    """Test a catalog answer without usable entries does not make them all stale."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    assert not repository.data.installed
    # At startup nothing is known to be in the catalog yet
    marketplace.repositories._default_repositories.clear()
    marketplace.set_stage(MarketplaceStage.STARTUP)
    url = "https://data-v2.hacs.xyz/plugin/data.json"
    response_mocker.add(url, mocked_response(url, json_content=catalog))

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.PLUGIN
    )

    assert marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID) is repository


async def test_catalog_rename_follows_the_repository_id(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a repository renamed on GitHub keeps its updates under the new name."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    old_name = repository.data.full_name
    url = "https://data-v2.hacs.xyz/plugin/data.json"
    response_mocker.add(
        url,
        mocked_response(
            url,
            json_content={
                REPOSITORY_PLUGIN_ID: GOOD_COMMON_DATA
                | {
                    "full_name": "hacs-test-org/plugin-renamed",
                    "last_fetched": 2000000000,
                    "last_version": "9.0.0",
                }
            },
        ),
    )

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.PLUGIN
    )

    assert (
        marketplace.repositories.get_by_full_name("hacs-test-org/plugin-renamed")
        is repository
    )
    assert marketplace.repositories.get_by_full_name(old_name) is None
    assert repository.data.last_version == "9.0.0"
    assert marketplace.common.renamed_repositories == {
        old_name: "hacs-test-org/plugin-renamed"
    }
