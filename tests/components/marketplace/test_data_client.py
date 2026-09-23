"""Tests for the Marketplace data client."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from http import HTTPStatus
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marketplace.base import StoreManager
from homeassistant.components.marketplace.exceptions import NotModifiedError, StoreError
from homeassistant.core import HomeAssistant

from . import (
    CategoryTestData,
    category_test_data_parametrized,
    get_store,
    mocked_response,
)
from .conftest import StoreResponses

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMockResponse

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
    store: StoreManager,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the repository data of every category."""
    result = await store.data_client.get_data(
        category_test_data["category"], validate=True
    )

    assert result == snapshot


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_get_repositories(
    store: StoreManager,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the repository list of every category."""
    result = await store.data_client.get_repositories(category_test_data["category"])

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
    store: StoreManager,
    response_mocker: StoreResponses,
    exception: Exception,
    message: str,
) -> None:
    """Test the errors a failing request is reported as."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    response_mocker.add(
        url, AiohttpClientMockResponse("get", url, exc=exception), keep=True
    )

    with pytest.raises(StoreError, match=message):
        await store.data_client.get_repositories("integration")


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
        pytest.param(HTTPStatus.BAD_REQUEST, pytest.raises(StoreError), id="400"),
        pytest.param(HTTPStatus.UNAUTHORIZED, pytest.raises(StoreError), id="401"),
        pytest.param(HTTPStatus.FORBIDDEN, pytest.raises(StoreError), id="403"),
        pytest.param(HTTPStatus.TOO_MANY_REQUESTS, pytest.raises(StoreError), id="429"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            pytest.raises(StoreError),
            id="500",
        ),
    ],
)
async def test_request_status_handling(
    store: StoreManager,
    response_mocker: StoreResponses,
    status: HTTPStatus,
    expectation: AbstractContextManager[Any],
) -> None:
    """Test which response status codes are treated as an error."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    response_mocker.add(
        url, mocked_response(url, status=status, json_content=[]), keep=True
    )

    with expectation:
        await store.data_client.get_repositories("integration")


async def test_etag_is_sent_back(
    store: StoreManager, response_mocker: StoreResponses
) -> None:
    """Test that the etag of a response is used for the next request."""
    url = "https://data-v2.hacs.xyz/integration/repositories.json"
    await store.data_client.get_repositories("integration")

    response_mocker.add(
        url, mocked_response(url, status=HTTPStatus.NOT_MODIFIED), keep=True
    )

    with pytest.raises(NotModifiedError):
        await store.data_client.get_repositories("integration")


@pytest.mark.parametrize(
    ("section", "data"),
    [
        pytest.param(
            "appdaemon",
            {"12345": _without_description(GOOD_COMMON_DATA)},
            id="appdaemon",
        ),
        pytest.param(
            "integration",
            {"12345": _without_description(GOOD_INTEGRATION_DATA)},
            id="integration",
        ),
        pytest.param(
            "plugin", {"12345": _without_description(GOOD_COMMON_DATA)}, id="plugin"
        ),
        pytest.param(
            "python_script",
            {"12345": _without_description(GOOD_COMMON_DATA)},
            id="python_script",
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
    store: StoreManager,
    response_mocker: StoreResponses,
    section: str,
    data: dict[str, Any] | list[Any],
) -> None:
    """Test that invalid data is dropped when validation is on, and kept when off."""
    url = f"https://data-v2.hacs.xyz/{section}/data.json"

    response_mocker.add(url, mocked_response(url, json_content=data))
    assert await store.data_client.get_data(section, validate=True) in ({}, [])

    response_mocker.add(url, mocked_response(url, json_content=data))
    assert await store.data_client.get_data(section, validate=False) == data


async def test_unknown_section_can_not_be_validated(
    store: StoreManager, response_mocker: StoreResponses
) -> None:
    """Test that a section without a schema is refused."""
    url = "https://data-v2.hacs.xyz/unknown/data.json"
    response_mocker.add(url, mocked_response(url, json_content=[]))

    with pytest.raises(ValueError, match="Do not know how to validate unknown"):
        await store.data_client.get_data("unknown", validate=True)


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_invalid_repository_data_is_not_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    response_mocker: StoreResponses,
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

    store = get_store(hass)
    assert not store.system.disabled
    assert store.stage == "running"
    assert store.repositories.get_by_full_name(category_test_data["repository"]) is None
