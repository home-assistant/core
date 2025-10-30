"""Tests for the Overseerr services."""

from unittest.mock import AsyncMock

import pytest
from python_overseerr import OverseerrConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overseerr.const import (
    ATTR_REQUESTED_BY,
    ATTR_SORT_ORDER,
    ATTR_STATUS,
    DOMAIN,
)
from homeassistant.components.overseerr.services import (
    ATTR_QUERY,
    SERVICE_GET_REQUESTS,
    SERVICE_SEARCH_MEDIA,
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

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_QUERY: "test",
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"results": []}
    mock_overseerr_client.search.assert_called_once_with("test")

    # Reset mock
    mock_overseerr_client.search.reset_mock()

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
    mock_overseerr_client.search.assert_called_once_with("test%20query%20with%20spaces")


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
        (SERVICE_SEARCH_MEDIA, {ATTR_QUERY: "test"}),
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
