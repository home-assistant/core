"""Test entry setup, token handling, access failures, and unloading."""

from unittest.mock import MagicMock

from google.auth.exceptions import RefreshError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_docs.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import DOCUMENT_ID, TOKEN_URI, http_error


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_api: dict[str, MagicMock],
) -> None:
    """Setup checks access and unload leaves the Google document intact."""
    assert setup_integration.state is ConfigEntryState.LOADED
    mock_api["get_document"].assert_called_once_with(
        "mock-access-token", DOCUMENT_ID, False
    )
    assert hass.services.has_service(DOMAIN, "append_text")
    assert hass.services.has_service(DOMAIN, "get_text")
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_api["create_document"].assert_not_called()


@pytest.mark.usefixtures("setup_credentials", "mock_api")
@pytest.mark.parametrize(
    "scope", ["", "https://www.googleapis.com/auth/drive.file-extra"]
)
async def test_missing_scope(
    hass: HomeAssistant, config_entry: MockConfigEntry, scope: str
) -> None:
    """Only the exact required scope satisfies setup."""
    config_entry.data["token"]["scope"] = scope
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.flow.async_progress() == []


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("error", "state"),
    [
        (http_error(401), ConfigEntryState.SETUP_ERROR),
        (RefreshError("Expired"), ConfigEntryState.SETUP_ERROR),
        (http_error(403), ConfigEntryState.SETUP_ERROR),
        (http_error(404), ConfigEntryState.SETUP_ERROR),
        (http_error(429), ConfigEntryState.SETUP_RETRY),
        (http_error(503), ConfigEntryState.SETUP_RETRY),
        (TimeoutError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_document_access_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: dict[str, MagicMock],
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Access failures do not create replacement documents or loop on a deleted one."""
    mock_api["get_document"].side_effect = error
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is state
    assert hass.config_entries.flow.async_progress() == []
    mock_api["create_document"].assert_not_called()


@pytest.mark.usefixtures("setup_credentials", "mock_api")
async def test_expired_token_is_refreshed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The HA OAuth session refreshes credentials before contacting Docs."""
    config_entry.data["token"]["expires_at"] = 0
    aioclient_mock.post(
        TOKEN_URI,
        json={"access_token": "new-token", "expires_in": 3600},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.data["token"]["access_token"] == "new-token"


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("status", "error", "state"),
    [
        pytest.param(400, None, ConfigEntryState.SETUP_ERROR, id="invalid-grant"),
        pytest.param(503, None, ConfigEntryState.SETUP_RETRY, id="server-error"),
        pytest.param(200, TimeoutError(), ConfigEntryState.SETUP_RETRY, id="timeout"),
    ],
)
async def test_refresh_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_api: dict[str, MagicMock],
    status: int,
    error: Exception | None,
    state: ConfigEntryState,
) -> None:
    """Permanent token failure stops setup while temporary failure retries it."""
    config_entry.data["token"]["expires_at"] = 0
    aioclient_mock.post(
        TOKEN_URI, status=status, json={"error": "invalid_grant"}, exc=error
    )
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is state
    assert hass.config_entries.flow.async_progress() == []
    mock_api["get_document"].assert_not_called()
    mock_api["create_document"].assert_not_called()
