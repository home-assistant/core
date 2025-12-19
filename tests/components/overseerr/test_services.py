"""Tests for the Overseerr services."""

import dataclasses
from unittest.mock import AsyncMock

import pytest
from python_overseerr import OverseerrConnectionError
from python_overseerr.models import MediaType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overseerr.const import (
    ATTR_LIMIT,
    ATTR_MEDIA_TYPE,
    ATTR_REQUESTED_BY,
    ATTR_SEASONS,
    ATTR_SORT_ORDER,
    ATTR_STATUS,
    ATTR_TMDB_ID,
    DOMAIN,
)
from homeassistant.components.overseerr.services import (
    ATTR_QUERY,
    SERVICE_GET_REQUESTS,
    SERVICE_REQUEST_MEDIA,
    SERVICE_SEARCH_AND_REQUEST,
    SERVICE_SEARCH_MEDIA,
    parse_seasons_input,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_service_get_requests(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_requests service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_STATUS: "approved",
            ATTR_SORT_ORDER: "added",
            ATTR_REQUESTED_BY: 1,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    for request in response["requests"]:
        assert "requests" not in request["media"]["media_info"]
    mock_overseerr_client.get_requests.assert_called_once_with(
        status="approved", sort="added", requested_by=1
    )


async def test_service_get_requests_no_meta(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_requests service."""
    mock_overseerr_client.get_movie_details.side_effect = OverseerrConnectionError
    mock_overseerr_client.get_tv_details.side_effect = OverseerrConnectionError

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    for request in response["requests"]:
        assert request["media"] == {}


async def test_service_search_media(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the search_media service."""
    # Mock the search method
    mock_overseerr_client.search.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Test with a query containing spaces
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_QUERY: "test query with spaces",
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"results": []}
    mock_overseerr_client.search.assert_called_once_with("test query with spaces")


async def test_service_search_media_with_limit(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the "limit" function of the search_media service."""

    @dataclasses.dataclass
    class SearchResultMock:
        name: str

    mock_overseerr_client.search.return_value = [
        SearchResultMock(name="Result 1"),
        SearchResultMock(name="Result 2"),
        SearchResultMock(name="Result 3"),
    ]

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_QUERY: "test",
            ATTR_LIMIT: 2,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"results": [{"name": "Result 1"}, {"name": "Result 2"}]}


async def test_service_request_media(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the request_media service."""

    # Mock the create request method
    @dataclasses.dataclass
    class RequestWithMediaMock:
        tmdb_id: str = "123456789"
        media_type: MediaType = MediaType.TV

    mock_overseerr_client.create_request.return_value = RequestWithMediaMock()

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_REQUEST_MEDIA,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_MEDIA_TYPE: "tv",
            ATTR_TMDB_ID: "123456789",
            ATTR_SEASONS: "1",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"request": {"media_type": MediaType.TV, "tmdb_id": "123456789"}}


async def test_service_search_and_request(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the search_and_request service."""

    @dataclasses.dataclass
    class SearchResultMock:
        title: str
        id: int
        media_type: MediaType = MediaType.TV

    mock_overseerr_client.search.return_value = [
        SearchResultMock(title="Result 1", id=1),
        SearchResultMock(title="Result 2", id=2),
    ]

    @dataclasses.dataclass
    class CreateRequestMock:
        pass

    mock_overseerr_client.create_request.return_value = CreateRequestMock()

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_AND_REQUEST,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_QUERY: "test",
            ATTR_SEASONS: "1",
        },
        blocking=True,
        return_response=True,
    )

    mock_overseerr_client.search.assert_called_once_with("test")
    mock_overseerr_client.create_request.assert_called_once_with(MediaType.TV, 1, [1])
    assert response == {
        "request": {},
        "media": {"type": MediaType.TV, "id": 1, "title": "Result 1"},
    }


async def test_service_search_and_request_with_no_results(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the early exit if the search yielded no results."""
    mock_overseerr_client.search.return_value = []

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(
        HomeAssistantError, match='The provided query "test" did not yield any results'
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_AND_REQUEST,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_QUERY: "test",
                ATTR_SEASONS: "1",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "payload", "function", "exception", "raised_exception", "message"),
    [
        (
            SERVICE_GET_REQUESTS,
            {},
            "get_requests",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
        (
            SERVICE_SEARCH_MEDIA,
            {ATTR_QUERY: "test"},
            "search",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
        (
            SERVICE_REQUEST_MEDIA,
            {ATTR_MEDIA_TYPE: "tv", ATTR_TMDB_ID: "123456789", ATTR_SEASONS: "1"},
            "create_request",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
    ],
)
async def test_services_connection_error(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
    function: str,
    exception: Exception,
    raised_exception: type[Exception],
    message: str,
) -> None:
    """Test a connection error in the services."""

    await setup_integration(hass, mock_config_entry)

    getattr(mock_overseerr_client, function).side_effect = exception

    with pytest.raises(raised_exception, match=message):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (SERVICE_GET_REQUESTS, {}),
        (SERVICE_SEARCH_MEDIA, {ATTR_QUERY: "test", ATTR_LIMIT: 3}),
        (
            SERVICE_REQUEST_MEDIA,
            {ATTR_MEDIA_TYPE: "tv", ATTR_TMDB_ID: "123456789", ATTR_SEASONS: "1"},
        ),
        (SERVICE_SEARCH_AND_REQUEST, {ATTR_QUERY: "test", ATTR_SEASONS: "1"}),
    ],
)
async def test_service_entry_availability(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
) -> None:
    """Test the services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        ServiceValidationError, match='Integration "overseerr" not found in registry'
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("seasons_input", "expected_seasons"),
    [
        ("1", [1]),
        ("1,", [1]),
        ("1,2,3", [1, 2, 3]),
        ("1, 2, 3", [1, 2, 3]),
        (" 1 ,     2,  3    ", [1, 2, 3]),
        ("[1]", [1]),
        ("[1,2,3]", [1, 2, 3]),
        ("[  1  , 2 ,    3]", [1, 2, 3]),
        ("", "all"),
        ("  ", "all"),
        ("Not a valid input", "all"),
        ("-", "all"),
    ],
)
def test_parse_seasons_input(seasons_input, expected_seasons) -> None:
    """Test that all inputs are parsed correctly."""
    assert expected_seasons == parse_seasons_input(seasons_input)
