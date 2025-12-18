"""Tests for the Overseerr services."""

from unittest.mock import AsyncMock

import pytest
from python_overseerr import OverseerrConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overseerr.const import (
    ATTR_ISSUE_ID,
    ATTR_ISSUE_TYPE,
    ATTR_MEDIA_ID,
    ATTR_MESSAGE,
    ATTR_REQUESTED_BY,
    ATTR_SORT_ORDER,
    ATTR_STATUS,
    DOMAIN,
)
from homeassistant.components.overseerr.services import (
    SERVICE_CREATE_ISSUE,
    SERVICE_DELETE_ISSUE,
    SERVICE_GET_ISSUES,
    SERVICE_GET_REQUESTS,
    SERVICE_UPDATE_ISSUE,
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
        )
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


async def test_service_get_issues(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_issues service."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ISSUES,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_overseerr_client.get_issues.assert_called_once_with(status=None)


async def test_service_get_issues_filtered(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_issues service with status filter."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ISSUES,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_STATUS: "open",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_overseerr_client.get_issues.assert_called_once_with(status="open")


async def test_service_create_issue(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the create_issue service."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_ISSUE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ISSUE_TYPE: "video",
            ATTR_MESSAGE: "Video quality is poor",
            ATTR_MEDIA_ID: 550,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    assert mock_overseerr_client.create_issue.called
    # Verify the enum was properly mapped
    call_args = mock_overseerr_client.create_issue.call_args
    assert call_args[1]["message"] == "Video quality is poor"
    assert call_args[1]["media_id"] == 550


async def test_service_update_issue_status(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the update_issue service with status change."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_ISSUE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ISSUE_ID: 1,
            ATTR_STATUS: "resolved",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    assert mock_overseerr_client.update_issue.called
    call_args = mock_overseerr_client.update_issue.call_args
    assert call_args[1]["issue_id"] == 1


async def test_service_update_issue_comment(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the update_issue service with comment."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_ISSUE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ISSUE_ID: 1,
            ATTR_MESSAGE: "This has been fixed",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    assert mock_overseerr_client.update_issue.called
    call_args = mock_overseerr_client.update_issue.call_args
    assert call_args[1]["message"] == "This has been fixed"


async def test_service_delete_issue(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the delete_issue service."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_ISSUE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_ISSUE_ID: 1,
        },
        blocking=True,
        return_response=False,
    )
    assert response is None
    mock_overseerr_client.delete_issue.assert_called_once_with(issue_id=1)


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
            SERVICE_GET_ISSUES,
            {},
            "get_issues",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
        (
            SERVICE_CREATE_ISSUE,
            {
                ATTR_ISSUE_TYPE: "video",
                ATTR_MESSAGE: "Test message",
                ATTR_MEDIA_ID: 550,
            },
            "create_issue",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
        (
            SERVICE_UPDATE_ISSUE,
            {ATTR_ISSUE_ID: 1, ATTR_STATUS: "resolved"},
            "update_issue",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
        (
            SERVICE_DELETE_ISSUE,
            {ATTR_ISSUE_ID: 1},
            "delete_issue",
            OverseerrConnectionError("Timeout"),
            HomeAssistantError,
            "Error connecting to the Overseerr instance: Timeout",
        ),
    ],
)
async def test_services_connection_error_all(
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
    """Test connection errors in all services."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_overseerr_client, function).side_effect = exception

    # delete_issue doesn't return a response
    return_response = service != SERVICE_DELETE_ISSUE

    with pytest.raises(raised_exception, match=message):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=return_response,
        )


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (SERVICE_GET_REQUESTS, {}),
        (SERVICE_GET_ISSUES, {}),
        (
            SERVICE_CREATE_ISSUE,
            {
                ATTR_ISSUE_TYPE: "video",
                ATTR_MESSAGE: "Test",
                ATTR_MEDIA_ID: 550,
            },
        ),
        (SERVICE_UPDATE_ISSUE, {ATTR_ISSUE_ID: 1, ATTR_STATUS: "resolved"}),
        (SERVICE_DELETE_ISSUE, {ATTR_ISSUE_ID: 1}),
    ],
)
async def test_service_entry_availability_all(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
) -> None:
    """Test all services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # delete_issue doesn't return a response
    return_response = service != SERVICE_DELETE_ISSUE

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=return_response,
        )

    with pytest.raises(
        ServiceValidationError, match='Integration "overseerr" not found in registry'
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=return_response,
        )
