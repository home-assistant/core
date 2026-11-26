"""Test Volvo init."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.auth import (
    LEGACY_VOLVOID_SERVER,
    VOLVOID_MIGRATION_URL,
    VOLVOID_SERVER,
)
from volvocarsapi.models import VolvoAuthException

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import configure_mock
from .const import LEGACY_CLIENT_ID, MOCK_ACCESS_TOKEN, SERVER_TOKEN_RESPONSE

VOLVOID_MIGRATION_ISSUE_ID = "volvoid_migration_{entry_id}"


@pytest.mark.usefixtures("mock_api")
async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test setting up the integration."""
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    assert await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_api")
async def test_token_refresh_success(
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test where token refresh succeeds."""

    assert mock_config_entry.data[CONF_TOKEN]["access_token"] == MOCK_ACCESS_TOKEN

    assert await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify token
    assert len(aioclient_mock.mock_calls) == 1
    assert (
        mock_config_entry.data[CONF_TOKEN]["access_token"]
        == SERVER_TOKEN_RESPONSE["access_token"]
    )


@pytest.mark.parametrize(
    ("token_response"),
    [
        (HTTPStatus.INTERNAL_SERVER_ERROR),
        (HTTPStatus.NOT_FOUND),
    ],
)
async def test_token_refresh_fail(
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
    token_response: HTTPStatus,
) -> None:
    """Test where token refresh fails."""

    aioclient_mock.post(VOLVOID_SERVER.token_url, status=token_response)

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("token_response"),
    [
        (HTTPStatus.BAD_REQUEST),
        (HTTPStatus.FORBIDDEN),
    ],
)
async def test_token_refresh_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
    token_response: HTTPStatus,
) -> None:
    """Test where token refresh indicates unauthorized."""

    aioclient_mock.post(VOLVOID_SERVER.token_url, status=token_response)

    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert flows
    assert flows[0]["handler"] == DOMAIN
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_no_vehicle(
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test no vehicle during coordinator setup."""
    mock_method: AsyncMock = mock_api.async_get_vehicle_details

    configure_mock(mock_method, return_value=None, side_effect=None)
    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_vehicle_auth_failure(
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test auth failure during coordinator setup."""
    mock_method: AsyncMock = mock_api.async_get_vehicle_details

    configure_mock(mock_method, return_value=None, side_effect=VolvoAuthException())
    assert not await setup_integration()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.volvo.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("client_id", [LEGACY_CLIENT_ID])
@pytest.mark.parametrize(
    ("token_response", "expected_state"),
    [
        pytest.param(HTTPStatus.OK, ConfigEntryState.LOADED, id="setup_succeeds"),
        pytest.param(
            HTTPStatus.BAD_REQUEST, ConfigEntryState.SETUP_ERROR, id="refresh_fails"
        ),
    ],
)
@pytest.mark.usefixtures("mock_api")
async def test_volvoid_migration_issue_created(
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: Callable[[], Awaitable[bool]],
    token_response: HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test that a legacy credential raises the Volvo ID migration issue."""
    aioclient_mock.post(
        LEGACY_VOLVOID_SERVER.token_url,
        status=token_response,
        json=SERVER_TOKEN_RESPONSE,
    )

    await setup_integration()
    assert mock_config_entry.state is expected_state

    issue = issue_registry.async_get_issue(
        DOMAIN,
        VOLVOID_MIGRATION_ISSUE_ID.format(entry_id=mock_config_entry.entry_id),
    )
    assert issue is not None
    assert issue.is_fixable
    assert not issue.is_persistent
    assert issue.learn_more_url == VOLVOID_MIGRATION_URL
    assert issue.data == {"entry_id": mock_config_entry.entry_id}


@pytest.mark.usefixtures("mock_api")
async def test_volvoid_migration_issue_deleted(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test that a new credential removes the Volvo ID migration issue."""
    issue_id = VOLVOID_MIGRATION_ISSUE_ID.format(entry_id=mock_config_entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="volvoid_migration",
        translation_placeholders={"name": mock_config_entry.title},
    )

    assert await setup_integration()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize("client_id", [LEGACY_CLIENT_ID])
@pytest.mark.usefixtures("mock_api")
async def test_volvoid_migration_issue_removed_with_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test that removing the entry removes the Volvo ID migration issue."""
    issue_id = VOLVOID_MIGRATION_ISSUE_ID.format(entry_id=mock_config_entry.entry_id)
    assert await setup_integration()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
