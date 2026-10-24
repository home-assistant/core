"""Test OAuth setup and reauthentication through the actual HA config flow."""

from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp.test_utils import TestClient
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_docs.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.components.google_docs.const import DEFAULT_ACCESS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .common import DOCUMENT_ID, TOKEN_URI, http_error

pytestmark = pytest.mark.usefixtures("current_request_with_host", "mock_api")


async def finish_oauth(
    hass: HomeAssistant,
    client: TestClient,
    aioclient_mock: AiohttpClientMocker,
    result: dict[str, Any],
    scope: str = DEFAULT_ACCESS,
) -> dict[str, Any]:
    """Complete the external OAuth callback with a fake Google token response."""
    state = parse_qs(urlparse(result["url"]).query)["state"][0]
    response = await client.get(
        "/auth/external/callback", params={"code": "test-code", "state": state}
    )
    assert response.status == 200
    aioclient_mock.post(
        TOKEN_URI,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": scope,
        },
    )
    with patch(
        "homeassistant.components.google_docs.async_setup_entry", return_value=None
    ):
        return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("setup_credentials")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
) -> None:
    """Authorization requests the Sheets scope and creates exactly one document."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    query = parse_qs(urlparse(result["url"]).query)
    assert query["scope"] == [DEFAULT_ACCESS]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Docs"
    assert result["result"].unique_id == DOCUMENT_ID
    assert result["result"].data["token"]["refresh_token"] == "new-refresh-token"
    assert result["description_placeholders"] == {
        "url": f"https://docs.google.com/document/d/{DOCUMENT_ID}/edit"
    }
    mock_api["create_document"].assert_called_once_with(
        "new-access-token", "Home Assistant"
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_missing_credentials(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Setup succeeds after the missing application credentials are supplied."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client-id", "client-secret"), DOMAIN
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOCUMENT_ID


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize("error", [http_error(403), TimeoutError()])
async def test_create_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
    error: Exception,
) -> None:
    """Creation failure leaves no entry and setup succeeds after recovery."""
    mock_api["create_document"].side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "create_document_failure"
    assert hass.config_entries.async_entries(DOMAIN) == []

    mock_api["create_document"].side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOCUMENT_ID
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("setup_credentials")
async def test_missing_scope(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
) -> None:
    """Setup succeeds after the required authorization scope is granted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result, scope=""
    )
    assert result["reason"] == "missing_scope"
    mock_api["create_document"].assert_not_called()

    aioclient_mock.clear_requests()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOCUMENT_ID
    mock_api["create_document"].assert_called_once_with(
        "new-access-token", "Home Assistant"
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_reauth_preserves_document(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
) -> None:
    """Reauthentication reconnects the existing document without creating another."""
    config_entry.add_to_hass(hass)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flow = hass.config_entries.flow.async_progress()[0]
    assert flow["step_id"] == "reauth_confirm"
    confirm = await hass.config_entries.flow.async_configure(flow["flow_id"])
    assert confirm["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["reason"] == "reauth_successful"
    assert config_entry.unique_id == DOCUMENT_ID
    assert config_entry.data["token"]["access_token"] == "new-access-token"
    mock_api["create_document"].assert_not_called()
    mock_api["get_document"].assert_called_once_with(
        "new-access-token", DOCUMENT_ID, False
    )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("error", "scope", "reason"),
    [
        pytest.param(
            http_error(404),
            DEFAULT_ACCESS,
            "open_document_failure",
            id="inaccessible-document",
        ),
        pytest.param(None, "", "missing_scope", id="missing-scope"),
    ],
)
async def test_reauth_error_recovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
    error: Exception | None,
    scope: str,
    reason: str,
) -> None:
    """Reauthentication preserves the original document through error recovery."""
    mock_api["get_document"].side_effect = error
    config_entry.add_to_hass(hass)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result, scope=scope
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert config_entry.unique_id == DOCUMENT_ID
    assert config_entry.data["token"]["access_token"] == "mock-access-token"
    mock_api["create_document"].assert_not_called()

    mock_api["get_document"].side_effect = None
    aioclient_mock.clear_requests()
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flow = hass.config_entries.flow.async_progress()[0]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["reason"] == "reauth_successful"
    assert config_entry.unique_id == DOCUMENT_ID
    assert config_entry.data["token"]["access_token"] == "new-access-token"
    mock_api["get_document"].assert_called_with("new-access-token", DOCUMENT_ID, False)
    mock_api["create_document"].assert_not_called()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("setup_credentials")
async def test_second_entry_uses_a_separate_document(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
) -> None:
    """The same Google account can configure more than one document entry."""
    config_entry.add_to_hass(hass)
    mock_api["create_document"].return_value = {
        "documentId": "second-document",
        "title": "Home Assistant",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["result"].unique_id == "second-document"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


@pytest.mark.usefixtures("setup_credentials")
async def test_duplicate_document_is_rejected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A returned document ID cannot be configured twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await finish_oauth(
        hass, await hass_client_no_auth(), aioclient_mock, result
    )
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_credential_help(hass: HomeAssistant) -> None:
    """Setup help links to the correct API and OAuth credentials pages."""
    placeholders = await async_get_description_placeholders(hass)
    assert placeholders["docs_api_url"].endswith("/docs.googleapis.com")
    assert placeholders["oauth_creds_url"].endswith("/apis/credentials")
