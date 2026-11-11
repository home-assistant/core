"""Tests for the Overseerr services."""

import dataclasses
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from python_overseerr import OverseerrConnectionError
from python_overseerr.models import MediaType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.components.overseerr.services import (
    OverseerrService,
    OverseerrServiceArgument,
    parse_seasons_input,
)
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration


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
        OverseerrService.GET_REQUESTS,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            OverseerrServiceArgument.STATUS: "approved",
            OverseerrServiceArgument.SORT_ORDER: "added",
            OverseerrServiceArgument.REQUESTED_BY: 1,
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
        OverseerrService.GET_REQUESTS,
        {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    for request in response["requests"]:
        assert request["media"] == {}


async def test_service_search_media(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the search_media service."""
    # Mock the search method
    mock_overseerr_client.search.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Test with a query containing spaces
    response = await hass.services.async_call(
        DOMAIN,
        OverseerrService.SEARCH_MEDIA,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            OverseerrServiceArgument.QUERY: "test query with spaces",
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"results": []}
    mock_overseerr_client.search.assert_called_once_with("test query with spaces")


async def test_service_request_media(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
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
        OverseerrService.REQUEST_MEDIA,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            OverseerrServiceArgument.MEDIA_TYPE: "tv",
            OverseerrServiceArgument.MEDIA_ID: "123456789",
            OverseerrServiceArgument.SEASONS: "1",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"request": {"media_type": MediaType.TV, "tmdb_id": "123456789"}}


@pytest.mark.parametrize(
    ("service", "payload", "function", "exception", "raised_exception", "message"),
    [
        (
            OverseerrService.GET_REQUESTS,
            {},
            "get_requests",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Seerr instance: Timeout",
        ),
        (
            OverseerrService.SEARCH_MEDIA,
            {OverseerrServiceArgument.QUERY: "test"},
            "search",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Seerr instance: Timeout",
        ),
        (
            OverseerrService.REQUEST_MEDIA,
            {
                OverseerrServiceArgument.MEDIA_TYPE: "tv",
                OverseerrServiceArgument.MEDIA_ID: "123456789",
                OverseerrServiceArgument.SEASONS: "1",
            },
            "create_request",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Seerr instance: Timeout",
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
            {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry.entry_id}
            | payload,
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (OverseerrService.GET_REQUESTS, {}),
        (OverseerrService.SEARCH_MEDIA, {OverseerrServiceArgument.QUERY: "test"}),
        (
            OverseerrService.REQUEST_MEDIA,
            {
                OverseerrServiceArgument.MEDIA_TYPE: "tv",
                OverseerrServiceArgument.MEDIA_ID: "123456789",
                OverseerrServiceArgument.SEASONS: "1",
            },
        ),
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

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {CommonServiceArgument.CONFIG_ENTRY_ID: mock_config_entry2.entry_id}
            | payload,
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {CommonServiceArgument.CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"


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
        (None, "all"),
        ("all", "all"),
        ("Not a valid input", "all"),
        ("-", "all"),
    ],
)
def test_parse_seasons_input(
    seasons_input: str | None, expected_seasons: list[int] | str
) -> None:
    """Test that all inputs are parsed correctly."""
    assert expected_seasons == parse_seasons_input(seasons_input)
